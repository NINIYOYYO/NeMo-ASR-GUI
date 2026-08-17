import asyncio
import bisect
import difflib
import json
import re
from typing import Any

import httpx
import openai

from interfaces import ITranslationService
from utils.logger import logger


class TranslationService(ITranslationService):
    """大模型处理服务：

    - 翻译：使用 ID-Map 映射法，彻底解决行数不匹配和错位问题。
    - 断句：使用纯文本处理与基于动态规划（DP）的锚点词时间戳对齐算法，消除累积漂移。
    """

    def __init__(self) -> None:
        """初始化翻译服务。"""
        self.max_retries = 3

    def _extract_json(self, text: str) -> str:
        """从模型返回的 Markdown 或杂乱文本中提取纯 JSON 字符串。

        Args:
            text (str): 模型返回的原始文本。

        Returns:
            str: 提取到的最外层 JSON 文本，若未匹配则返回原文本。
        """
        try:
            # 寻找最外层的 {}
            match = re.search(r"\{.*\}", text, re.DOTALL)
            return match.group(0) if match else text
        except Exception:
            return text

    def _clean_text_response(self, text: str) -> str:
        """清洗纯文本响应，去除 Markdown 代码块标记。

        Args:
            text (str): 待清洗的原始文本。

        Returns:
            str: 清洗后的纯文本。
        """
        text = re.sub(r"^```\w*\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    async def _call_llm_async(
        self,
        prompt: str,
        api_key: str,
        base_url: str,
        model: str,
        proxy: str | None = None,
        is_json: bool = True,
    ) -> str:
        """底层异步调用大语言模型 API。

        Args:
            prompt (str): 输入提示词。
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model (str): 模型名称。
            proxy (str | None): 可选代理服务器地址。
            is_json (bool): 是否要求返回 JSON 格式。

        Returns:
            str: 模型返回的文本响应内容。

        Raises:
            ValueError: 当模型返回空内容或安全拦截时抛出。
            httpx.HTTPStatusError: 当 HTTP 请求返回非 2xx 状态码时抛出。
        """
        proxy_mounts = None
        if proxy and proxy.strip():
            proxy_mounts = {"all://": httpx.AsyncHTTPTransport(proxy=proxy.strip())}

        # 增加超时时间到 180秒
        timeout_val = 180.0

        # 1. 适配 Gemini 原生接口 (使用 HTTP Header x-goog-api-key 传输密钥，避免 URL Query 明文泄露)
        if "generativelanguage.googleapis.com" in base_url:
            url = f"{base_url.rstrip('/')}/models/{model}:generateContent"
            headers = {
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            }
            payload: dict[str, Any] = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json" if is_json else "text/plain",
                    "temperature": 0.1,  # 低温保证稳定
                },
            }
            if "thinking" in model.lower():
                payload["generationConfig"]["thinkingConfig"] = {"includeThoughts": False}

            async with httpx.AsyncClient(
                mounts=proxy_mounts, timeout=timeout_val, headers=headers
            ) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                result = resp.json()
                try:
                    candidates = result.get("candidates", [])
                    if not candidates or "content" not in candidates[0]:
                        raise ValueError(f"Gemini 返回空结果 (可能触发安全拦截): {result}")
                    return candidates[0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    raise ValueError(f"Gemini 返回格式异常: {result}") from None

        # 2. 适配 OpenAI 兼容接口 (硅基流动/DeepSeek等)
        else:
            async with httpx.AsyncClient(
                mounts=proxy_mounts, timeout=timeout_val
            ) as http_client:
                async_client = openai.AsyncOpenAI(
                    api_key=api_key, base_url=base_url, http_client=http_client
                )
                extra_args = (
                    {"response_format": {"type": "json_object"}} if is_json else {}
                )

                response = await async_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    **extra_args,
                )
                return response.choices[0].message.content or ""

    async def _process_chunk_with_retry(
        self, chunk: list[dict[str, Any]], task_type: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """执行带有指数退避与 429 频控重试的核心处理任务。

        Args:
            chunk (list[dict[str, Any]]): 待处理的字幕段落块。
            task_type (str): 任务类型 ('translate' 或 'segment')。
            **kwargs: 附加参数 (api_key, base_url, model, target_lang, is_bilingual, proxy 等)。

        Returns:
            list[dict[str, Any]]: 处理完成的字幕段落列表。
        """
        api_key: str = kwargs["api_key"]
        base_url: str = kwargs["base_url"]
        model: str = kwargs["model"]
        proxy: str | None = kwargs.get("proxy")

        source_texts = [s["segment"] for s in chunk]

        for attempt in range(1, self.max_retries + 1):
            try:
                # =========================================================
                #  翻译任务：使用 ID 映射法 (Key-Value Mapping)
                #  解决 Qwen/小模型容易出现行数不匹配和错位的问题
                # =========================================================
                if task_type == "translate":
                    # 1. 构建输入字典 {"0": "text1", "1": "text2"}
                    input_map = {str(i): text for i, text in enumerate(source_texts)}

                    prompt = self._build_translation_prompt(
                        input_map, kwargs["target_lang"]
                    )

                    raw_response = await self._call_llm_async(
                        prompt, api_key, base_url, model, proxy, is_json=True
                    )

                    # 2. 解析返回的 JSON
                    try:
                        data = json.loads(self._extract_json(raw_response))
                    except json.JSONDecodeError:
                        raise ValueError(
                            f"模型未返回有效 JSON: {raw_response[:50]}..."
                        ) from None

                    # 3. 兼容性处理：有些模型会把结果包在 'translations' 键里，有些直接返回字典
                    result_map = data
                    if "translations" in data and isinstance(data["translations"], dict):
                        result_map = data["translations"]

                    res_chunk = []
                    # 4. 严格按 ID 取回结果
                    for i, seg in enumerate(chunk):
                        key = str(i)
                        original_text = seg["segment"]

                        # 尝试获取翻译
                        t_text = result_map.get(key)

                        # 简单清洗：如果翻译为空或只是个ID，回退原文
                        if not t_text or str(t_text).strip() == key:
                            t_text = original_text

                        new_seg = seg.copy()
                        # 组装双语
                        if kwargs.get("is_bilingual"):
                            if str(t_text).strip() == original_text.strip():
                                new_seg["segment"] = original_text
                            else:
                                new_seg["segment"] = f"{original_text}\n{str(t_text)}"
                        else:
                            new_seg["segment"] = str(t_text)

                        res_chunk.append(new_seg)

                    return res_chunk

                # =========================================================
                #  断句任务：纯文本模式 + 动态规划锚点对齐
                # =========================================================
                else:
                    prompt = self._build_segmentation_prompt(" ".join(source_texts))
                    raw_response = await self._call_llm_async(
                        prompt, api_key, base_url, model, proxy, is_json=False
                    )
                    processed_text = self._clean_text_response(raw_response)
                    return self._realign_timestamps(chunk, processed_text)

            except Exception as e:
                # 针对 429 错误的特殊处理
                wait_time = (2**attempt) + 1
                error_str = str(e)
                if "429" in error_str or "Too Many Requests" in error_str:
                    logger.warning("触发 API 频率限制 (429)，强制等待 20 秒...")
                    wait_time = 20

                logger.warning(
                    f"[重试 {attempt}/{self.max_retries}] {task_type} 失败: {e}. {wait_time}s 后重试..."
                )

                if attempt == self.max_retries:
                    logger.error(f"{task_type} 分块彻底失败，保全时间轴，返回原文")
                    return chunk

                await asyncio.sleep(wait_time)

        return chunk

    async def translate_segments(
        self,
        segments: list[dict[str, Any]],
        target_lang: str,
        api_key: str,
        base_url: str,
        model: str,
        is_bilingual: bool,
        proxy: str | None = None,
        concurrency: int = 5,
        chunk_size: int = 30,
    ) -> list[dict[str, Any]]:
        """并发调用大模型翻译字幕段落。

        Args:
            segments (list[dict[str, Any]]): 待翻译的字幕列表。
            target_lang (str): 目标语言名称。
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model (str): 模型名称。
            is_bilingual (bool): 是否生成双语字幕。
            proxy (str | None): 可选代理地址。
            concurrency (int): 最大并发任务数。
            chunk_size (int): 每个批次的段落数量。

        Returns:
            list[dict[str, Any]]: 翻译完成的字幕列表。
        """
        if not segments:
            return []
        semaphore = asyncio.Semaphore(concurrency)
        chunks = [
            segments[i : i + chunk_size] for i in range(0, len(segments), chunk_size)
        ]

        async def worker(c: list[dict[str, Any]]) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._process_chunk_with_retry(
                    c,
                    "translate",
                    target_lang=target_lang,
                    is_bilingual=is_bilingual,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    proxy=proxy,
                )

        logger.info(f"开始并行翻译: 总分块={len(chunks)}, 并发={concurrency}")
        tasks = [worker(c) for c in chunks]
        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]

    async def segment_subtitles(
        self,
        segments: list[dict[str, Any]],
        api_key: str,
        base_url: str,
        model: str,
        proxy: str | None = None,
        concurrency: int = 3,
        chunk_size: int = 50,
    ) -> list[dict[str, Any]]:
        """并发调用大模型进行智能断句重构。

        Args:
            segments (list[dict[str, Any]]): 待断句的字幕列表。
            api_key (str): API 密钥。
            base_url (str): API 基础 URL。
            model (str): 模型名称。
            proxy (str | None): 可选代理地址。
            concurrency (int): 最大并发任务数。
            chunk_size (int): 每个批次的段落数量。

        Returns:
            list[dict[str, Any]]: 断句与时间戳重对齐后的字幕列表。
        """
        if not segments:
            return []
        semaphore = asyncio.Semaphore(concurrency)
        chunks = [
            segments[i : i + chunk_size] for i in range(0, len(segments), chunk_size)
        ]

        async def worker(c: list[dict[str, Any]]) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._process_chunk_with_retry(
                    c,
                    "segment",
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    proxy=proxy,
                )

        logger.info(f"开始 AI 断句: 总分块={len(chunks)}, 并发={concurrency}")
        tasks = [worker(c) for c in chunks]
        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]

    def _build_translation_prompt(self, text_map: dict[str, str], target_lang: str) -> str:
        """构建强对齐的翻译提示词。

        Args:
            text_map (dict[str, str]): ID 与原文映射字典。
            target_lang (str): 目标语言。

        Returns:
            str: 格式化的提示词。
        """
        return f"""
        You are a subtitle translator.
        Task: Translate the values in the JSON object to {target_lang}.
        
        Rules:
        1. Keep the JSON keys (IDs) EXACTLY the same. 
        2. Translate the values.
        3. Do not merge or split lines. One ID corresponds to one line.
        4. Return ONLY the JSON object.
        
        Input:
        {json.dumps(text_map, ensure_ascii=False, indent=2)}
        """

    def _build_segmentation_prompt(self, raw_text: str) -> str:
        """构建智能断句提示词。

        Args:
            raw_text (str): 待断句的原始文本。

        Returns:
            str: 格式化的提示词。
        """
        return f"""
        Task: Insert logical breaks '|' into the text for video subtitles.
        
        Rules:
        1. Output ONLY the processed text. NO JSON, NO explanations.
        2. DO NOT change/delete/add words. ONLY insert '|'.
        3. Target segment length: 30-60 chars (flexible).
        4. Keep original punctuation.
        
        Input:
        {raw_text}
        """

    def align_timestamps(
        self, original_segments: list[dict[str, Any]], llm_text: str
    ) -> list[dict[str, Any]]:
        """基于动态规划与锚点词序列对齐算法重组时间戳（公开方法）。

        Args:
            original_segments (list[dict[str, Any]]): 包含已知时间戳的原始段落。
            llm_text (str): 包含 '|' 分隔符的大模型断句文本。

        Returns:
            list[dict[str, Any]]: 重对齐后的新段落列表。
        """
        return self._realign_timestamps(original_segments, llm_text)

    def _realign_timestamps(
        self, original_segments: list[dict[str, Any]], llm_text: str
    ) -> list[dict[str, Any]]:
        """基于动态规划（DP）与锚点词序列对齐算法，将大模型断句结果对齐到原始音频时间轴。

        通过 difflib.SequenceMatcher 建立原文字符与重构文本字符之间的非重叠最长单调匹配块，
        对匹配字符直接继承原始精确时间戳，对增删改的词句在相邻锚点间进行局部线性插值，彻底消除累积漂移。

        Args:
            original_segments (list[dict[str, Any]]): 包含已知时间戳的原始段落。
            llm_text (str): 包含 '|' 分隔符的大模型断句文本。

        Returns:
            list[dict[str, Any]]: 重对齐后的新段落列表。
        """
        if not original_segments:
            return []
        if not llm_text or "|" not in llm_text:
            return original_segments

        # 1. 提取原始字符级时间戳时间轴
        orig_chars: list[dict[str, Any]] = []
        for seg in original_segments:
            text = seg.get("segment", "")
            clean_text = re.sub(r"\s+", "", text)
            if not clean_text:
                continue

            duration = max(0.01, seg["end"] - seg["start"])
            char_duration = duration / len(clean_text)
            for i, char in enumerate(clean_text):
                c_start = seg["start"] + (i * char_duration)
                c_end = c_start + char_duration
                orig_chars.append({"char": char, "start": c_start, "end": c_end})

        if not orig_chars:
            return original_segments

        orig_str = "".join(c["char"] for c in orig_chars)
        orig_total_start = orig_chars[0]["start"]
        orig_total_end = orig_chars[-1]["end"]
        avg_char_dur = max(
            0.01, (orig_total_end - orig_total_start) / len(orig_chars)
        )

        # 2. 解析大模型返回的分段部分，记录各段在去空格合并串中的起止索引
        raw_parts = [p.strip() for p in llm_text.split("|")]
        part_spans: list[tuple[int, int, str]] = []
        part_clean_texts: list[str] = []
        curr_pos = 0

        for p in raw_parts:
            clean_p = re.sub(r"\s+", "", p)
            if not clean_p:
                continue
            p_len = len(clean_p)
            part_spans.append((curr_pos, curr_pos + p_len, p))
            part_clean_texts.append(clean_p)
            curr_pos += p_len

        if not part_spans:
            return original_segments

        llm_clean_str = "".join(part_clean_texts)
        llm_len = len(llm_clean_str)

        # 3. 基于动态规划（LCS/SequenceMatcher）寻找单调锚点块
        matcher = difflib.SequenceMatcher(
            None, orig_str, llm_clean_str, autojunk=False
        )
        matching_blocks = matcher.get_matching_blocks()

        matched_times: dict[int, tuple[float, float]] = {}
        for block in matching_blocks:
            orig_i, llm_j, size = block
            for k in range(size):
                o_idx = orig_i + k
                l_idx = llm_j + k
                if o_idx < len(orig_chars):
                    matched_times[l_idx] = (
                        orig_chars[o_idx]["start"],
                        orig_chars[o_idx]["end"],
                    )

        # 4. 对未匹配的字符在相邻锚点间进行局部线性插值与平滑外推
        sorted_matched_indices = sorted(matched_times.keys())
        full_llm_times: list[tuple[float, float]] = []

        if not sorted_matched_indices:
            # 极端情况：完全无匹配字符，按比例均分时间
            total_dur = max(0.1, orig_total_end - orig_total_start)
            dur_per_char = total_dur / llm_len
            for l_idx in range(llm_len):
                s = orig_total_start + l_idx * dur_per_char
                e = s + dur_per_char
                full_llm_times.append((s, e))
        else:
            for l_idx in range(llm_len):
                if l_idx in matched_times:
                    full_llm_times.append(matched_times[l_idx])
                else:
                    pos = bisect.bisect_left(sorted_matched_indices, l_idx)
                    if pos == 0:
                        # 位于首个锚点前，向前外推
                        first_idx = sorted_matched_indices[0]
                        first_start = matched_times[first_idx][0]
                        offset = (first_idx - l_idx) * avg_char_dur
                        s = max(orig_total_start, first_start - offset)
                        e = s + avg_char_dur
                        full_llm_times.append((s, e))
                    elif pos == len(sorted_matched_indices):
                        # 位于末尾锚点后，向后外推
                        last_idx = sorted_matched_indices[-1]
                        last_end = matched_times[last_idx][1]
                        offset = (l_idx - last_idx) * avg_char_dur
                        s = min(orig_total_end, last_end + offset - avg_char_dur)
                        e = min(orig_total_end + avg_char_dur, s + avg_char_dur)
                        full_llm_times.append((s, e))
                    else:
                        # 位于两个锚点之间，线性插值
                        left_idx = sorted_matched_indices[pos - 1]
                        right_idx = sorted_matched_indices[pos]
                        left_end = matched_times[left_idx][1]
                        right_start = matched_times[right_idx][0]
                        span = max(1, right_idx - left_idx)
                        ratio = (l_idx - left_idx) / span
                        gap_dur = max(0.0, right_start - left_end)
                        s = left_end + ratio * gap_dur
                        e = s + avg_char_dur
                        full_llm_times.append((s, e))

        # 5. 组合生成新段落并进行单调性与最小间隔保护
        new_segments: list[dict[str, Any]] = []
        prev_end = orig_total_start

        for start_idx, end_idx, raw_text in part_spans:
            s_time = full_llm_times[start_idx][0]
            e_time = full_llm_times[end_idx - 1][1]

            # 保证时间不倒流
            if s_time < prev_end:
                s_time = prev_end

            # 保证字幕段落最小持续时间 (0.05s)
            min_span = max(0.05, (end_idx - start_idx) * 0.02)
            if e_time <= s_time:
                e_time = s_time + min_span

            new_segments.append(
                {
                    "start": round(s_time, 3),
                    "end": round(e_time, 3),
                    "segment": raw_text,
                }
            )
            prev_end = s_time

        if not new_segments:
            logger.warning("AI 断句对齐失败，回退到原始分段")
            return original_segments

        return new_segments
