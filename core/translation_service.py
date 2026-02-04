import openai
import httpx
import json
import asyncio
import re
from interfaces import ITranslationService
from utils.logger import logger

class TranslationService(ITranslationService):
    """
    大模型处理服务：
    - 翻译：使用 ID-Map 映射法，彻底解决行数不匹配和错位问题。
    - 断句：使用纯文本流式处理，解决超时问题。
    """

    def __init__(self):
        self.max_retries = 3

    def _extract_json(self, text: str) -> str:
        """从模型返回的 Markdown 或杂乱文本中提取纯 JSON。"""
        try:
            # 寻找最外层的 {}
            match = re.search(r"\{.*\}", text, re.DOTALL)
            return match.group(0) if match else text
        except Exception:
            return text
            
    def _clean_text_response(self, text: str) -> str:
        """清洗纯文本响应，去除 Markdown 代码块标记"""
        text = re.sub(r"^```\w*\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    async def _call_llm_async(
        self,
        prompt: str,
        api_key: str,
        base_url: str,
        model: str,
        proxy: str = None,
        is_json: bool = True,
    ):
        """底层异步调用"""
        proxy_mounts = None
        if proxy and proxy.strip():
            proxy_mounts = {"all://": httpx.AsyncHTTPTransport(proxy=proxy.strip())}

        # 增加超时时间到 180秒
        timeout_val = 180.0 

        # 1. 适配 Gemini 原生接口
        if "generativelanguage.googleapis.com" in base_url:
            url = f"{base_url}/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json" if is_json else "text/plain",
                    "temperature": 0.1, # 低温保证稳定
                },
            }
            if "thinking" in model.lower():
                payload["generationConfig"]["thinkingConfig"] = {"includeThoughts": False}

            async with httpx.AsyncClient(mounts=proxy_mounts, timeout=timeout_val) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                result = resp.json()
                try:
                    return result["candidates"][0]["content"]["parts"][0]["text"]
                except KeyError:
                    # 偶尔 Gemini 会因为安全原因返回空，抛出异常触发重试
                    raise ValueError(f"Gemini 返回空结果 (可能触发安全拦截): {result}")

        # 2. 适配 OpenAI 兼容接口 (硅基流动/DeepSeek等)
        else:
            async with httpx.AsyncClient(mounts=proxy_mounts, timeout=timeout_val) as http_client:
                async_client = openai.AsyncOpenAI(
                    api_key=api_key, base_url=base_url, http_client=http_client
                )
                extra_args = {"response_format": {"type": "json_object"}} if is_json else {}
                
                response = await async_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    **extra_args,
                )
                return response.choices[0].message.content

    async def _process_chunk_with_retry(self, chunk: list, task_type: str, **kwargs):
        """
        核心处理器
        """
        api_key = kwargs.get("api_key")
        base_url = kwargs.get("base_url")
        model = kwargs.get("model")
        proxy = kwargs.get("proxy")
        
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
                    
                    prompt = self._build_translation_prompt(input_map, kwargs.get("target_lang"))
                    
                    raw_response = await self._call_llm_async(
                        prompt, api_key, base_url, model, proxy, is_json=True
                    )
                    
                    # 2. 解析返回的 JSON
                    try:
                        data = json.loads(self._extract_json(raw_response))
                    except json.JSONDecodeError:
                        raise ValueError(f"模型未返回有效 JSON: {raw_response[:50]}...")
                    
                    # 3. 兼容性处理：有些模型会把结果包在 'translations' 键里，有些直接返回字典
                    result_map = data
                    if "translations" in data and isinstance(data["translations"], dict):
                        result_map = data["translations"]

                    res_chunk = []
                    # 4. 【核心逻辑】严格按 ID 取回结果
                    for i, seg in enumerate(chunk):
                        key = str(i)
                        original_text = seg["segment"]
                        
                        # 尝试获取翻译
                        # 如果模型漏掉了 ID '5'，这里 get 会返回 None，然后我们就用原文
                        t_text = result_map.get(key)
                        
                        # 简单清洗：如果翻译为空或只是个ID，回退原文
                        if not t_text or str(t_text).strip() == key:
                            t_text = original_text

                        new_seg = seg.copy()
                        # 组装双语
                        if kwargs.get("is_bilingual"):
                            # 防止翻译和原文一模一样时重复显示
                            if str(t_text).strip() == original_text.strip():
                                new_seg["segment"] = original_text
                            else:
                                new_seg["segment"] = f"{original_text}\n{str(t_text)}"
                        else:
                            new_seg["segment"] = str(t_text)
                            
                        res_chunk.append(new_seg)
                        
                    return res_chunk

                # =========================================================
                #  断句任务：纯文本模式
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
                wait_time = (2 ** attempt) + 1
                error_str = str(e)
                if "429" in error_str or "Too Many Requests" in error_str:
                    logger.warning(f"触发 API 频率限制 (429)，强制等待 20 秒...")
                    wait_time = 20

                logger.warning(f"[重试 {attempt}/{self.max_retries}] {task_type} 失败: {e}. {wait_time}s 后重试...")
                
                if attempt == self.max_retries:
                    logger.error(f"{task_type} 分块彻底失败，保全时间轴，返回原文")
                    return chunk 

                await asyncio.sleep(wait_time)

    async def translate_segments(
        self, segments: list, target_lang: str, api_key: str, base_url: str, model: str,
        is_bilingual: bool, proxy: str = None, concurrency: int = 5, chunk_size: int = 30,
    ):
        if not segments: return []
        semaphore = asyncio.Semaphore(concurrency)
        chunks = [segments[i : i + chunk_size] for i in range(0, len(segments), chunk_size)]

        async def worker(c):
            async with semaphore:
                return await self._process_chunk_with_retry(
                    c, "translate", target_lang=target_lang, is_bilingual=is_bilingual,
                    api_key=api_key, base_url=base_url, model=model, proxy=proxy,
                )

        logger.info(f"开始并行翻译: 总分块={len(chunks)}, 并发={concurrency}")
        tasks = [worker(c) for c in chunks]
        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]

    async def segment_subtitles(
        self, segments: list, api_key: str, base_url: str, model: str,
        proxy: str = None, concurrency: int = 3, chunk_size: int = 50,
    ):
        if not segments: return []
        semaphore = asyncio.Semaphore(concurrency)
        chunks = [segments[i : i + chunk_size] for i in range(0, len(segments), chunk_size)]

        async def worker(c):
            async with semaphore:
                return await self._process_chunk_with_retry(
                    c, "segment", api_key=api_key, base_url=base_url, model=model, proxy=proxy,
                )

        logger.info(f"开始 AI 断句: 总分块={len(chunks)}, 并发={concurrency}")
        tasks = [worker(c) for c in chunks]
        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]

    def _build_translation_prompt(self, text_map: dict, target_lang: str) -> str:
        # 使用 ID 映射 Prompt，强制模型对齐
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

    def _realign_timestamps(self, original_segments: list, llm_text: str) -> list:
        if not llm_text or "|" not in llm_text:
            return original_segments

        atomic_chars = []
        for seg in original_segments:
            text = seg["segment"]
            clean_text = text.replace(" ", "").replace("\n", "").replace("\r", "")
            if not clean_text: continue
            
            duration = seg["end"] - seg["start"]
            if len(clean_text) > 0:
                char_duration = duration / len(clean_text)
                for i, char in enumerate(clean_text):
                    c_start = seg["start"] + (i * char_duration)
                    c_end = c_start + char_duration
                    atomic_chars.append({"char": char, "start": c_start, "end": c_end})

        parts = llm_text.split("|")
        new_segments = []
        cursor = 0

        for part in parts:
            part_text = part.strip()
            if not part_text: continue

            part_len_clean = len(part_text.replace(" ", "").replace("\n", "").replace("\r", ""))
            if part_len_clean == 0: continue
            
            if cursor >= len(atomic_chars): break

            start_idx = cursor
            end_idx = min(cursor + part_len_clean, len(atomic_chars))
            
            start_time = atomic_chars[start_idx]["start"]
            end_time = atomic_chars[end_idx - 1]["end"]

            new_segments.append({
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "segment": part_text
            })
            cursor = end_idx

        if not new_segments:
            logger.warning("AI 断句对齐失败，回退到原始分段")
            return original_segments

        return new_segments