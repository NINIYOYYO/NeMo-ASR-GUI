"""Gradio Web 可视化用户界面模块。

组装模型加载、音视频转录、多格式字幕导出、字幕表格编辑及大模型翻译断句的 UI 组件与事件绑定。
"""

import os
from typing import Any

import gradio as gr
import torch

from core.constants import (
    AVAILABLE_MODELS,
    CHUNK_SLIDER_MAX,
    CHUNK_SLIDER_MIN,
    CHUNK_SLIDER_STEP,
    DEFAULT_CHUNK_LENGTH_S,
    DEFAULT_CLOUD_MODEL,
    DEFAULT_LANGUAGE,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    LLM_CHUNK_SIZE_DEFAULT,
    LLM_CHUNK_SIZE_MAX,
    LLM_CHUNK_SIZE_MIN,
    LLM_CHUNK_SIZE_STEP,
    LLM_CONCURRENCY_DEFAULT,
    LLM_CONCURRENCY_MAX,
    LLM_CONCURRENCY_MIN,
    LLM_CONCURRENCY_STEP,
    MAX_LINE_WIDTH_DEFAULT,
    MAX_LINE_WIDTH_MAX,
    MAX_LINE_WIDTH_MIN,
    MAX_LINE_WIDTH_STEP,
)
from interfaces import IApplication
from utils.logger import logger
from utils.translator import set_language, t

initial_model_status: str = t("model.not_loaded")


def create_ui(app: IApplication) -> gr.Blocks:
    """创建并装配 Gradio 用户界面。

    Args:
        app (IApplication): 应用程序的主实例，作为核心服务和控制器的统一入口。

    Returns:
        gr.Blocks: 装配完成的 Gradio UI 实例。
    """
    # --- 初始化配置 ---
    initial_config = app.config_manager.get_config_all()
    saved_model_path: str = initial_config.get("local_model_path", "") or ""
    saved_cloud_model: str = initial_config.get("cloud_model_name") or DEFAULT_CLOUD_MODEL
    saved_language: str = initial_config.get("language") or DEFAULT_LANGUAGE
    initial_chunk_length: int = initial_config.get("chunk_length_s") or DEFAULT_CHUNK_LENGTH_S

    saved_api_key: str = initial_config.get("api_key", "") or ""
    saved_base_url: str = initial_config.get("base_url", DEFAULT_LLM_BASE_URL) or DEFAULT_LLM_BASE_URL
    saved_llm_model: str = initial_config.get("llm_model", DEFAULT_LLM_MODEL) or DEFAULT_LLM_MODEL
    saved_proxy: str = initial_config.get("proxy", "") or ""

    # 设置初始语言
    set_language(saved_language)

    # --- 自动加载模型并设置初始状态 (国际化) ---
    global initial_model_status
    if saved_model_path is not None:
        try:
            if saved_model_path == "":  # NGC 模型
                logger.info(t("model.loading_cloud", model_name=saved_cloud_model))
                initial_model_status = app.asr_service.load_model_from_ngc(saved_cloud_model)
            elif os.path.exists(saved_model_path):  # 本地模型存在
                logger.info(t("model.loading_local", path=saved_model_path))
                initial_model_status = app.asr_service.load_model_from_local(saved_model_path)
            else:
                initial_model_status = t("model.error_path_not_found", path=saved_model_path)
        except Exception as e:
            logger.error(f"启动时自动加载模型失败: {e}")
            initial_model_status = f"自动加载模型失败: {e}"

    # --- 语言切换的核心函数 ---
    def change_language(lang: str) -> dict[Any, Any]:
        """切换全局语言并更新 UI 组件属性字典。

        Args:
            lang (str): 目标语言代码。

        Returns:
            dict[Any, Any]: 组件到属性更新对象的映射字典。
        """
        set_language(lang)
        app.config_manager.save_config(language=lang)
        return {
            title_md: gr.update(value=t("app.title")),
            app_description: gr.update(value=t("app.description")),
            model_settings_title: gr.update(label=t("model.settings_title")),
            model_cloud_section_title: gr.update(value=t("model.cloud_section_title")),
            cloud_model_dropdown: gr.update(label=t("model.cloud_model_label"), info=t("model.cloud_model_info")),
            model_description: gr.update(label=t("model.model_description_label")),
            load_cloud_model_button: gr.update(value=t("model.load_cloud_button")),
            model_local_section_title: gr.update(value=t("model.local_section_title")),
            local_model_path_input: gr.update(
                label=t("model.local_path_label"),
                placeholder=t("model.local_path_placeholder"),
            ),
            load_local_model_button: gr.update(value=t("model.load_local_button")),
            model_status_output: gr.update(label=t("model.status_label")),
            chunk_slider: gr.update(label=t("model.chunk_length_label"), info=t("model.chunk_length_info")),
            transcription_tab: gr.update(label=t("transcription.tab_title")),
            format_checkboxes: gr.update(label=t("transcription.format_label")),
            video_input: gr.update(label=t("transcription.upload_label")),
            media_submit_button: gr.update(value=t("transcription.submit_button")),
            status_output: gr.update(label=t("transcription.status_label")),
            subtitle_result_accordion: gr.update(label=t("transcription.result_title")),
            subtitle_file_output: gr.update(label=t("transcription.download_label")),
            subtitle_zip_download_button: gr.update(value=t("transcription.zip_button")),
            subtitle_preview_output: gr.update(label=t("transcription.preview_label")),
            speaker_diarization_tab: gr.update(label=t("diarization.tab_title")),
            enable_speaker_diarization_checkbox: gr.update(
                label=t("diarization.enable_label"), info=t("diarization.enable_info")
            ),
            diarization_dev_msg: gr.update(value=t("diarization.development_msg")),
            subtitle_editing_tab: gr.update(label=t("editing.tab_title")),
            subtitle_to_edit_input: gr.update(label=t("editing.upload_label")),
            correction_table: gr.update(
                label=t("editing.correction_table_label"),
                headers=[t("editing.table_header_error"), t("editing.table_header_correct")],
            ),
            apply_correction_btn: gr.update(value=t("editing.batch_replace_btn")),
            save_correction_btn: gr.update(value=t("editing.save_correction_btn")),
            editing_tips_md: gr.update(value=t("editing.tips")),
            subtitle_editor_df: gr.update(
                label=t("editing.data_label"),
                headers=[
                    t("editing.col_id"),
                    t("editing.col_start"),
                    t("editing.col_end"),
                    t("editing.col_text"),
                ],
            ),
            save_edit_button: gr.update(value=t("editing.save_subtitle_btn")),
            edited_file_output: gr.update(label=t("editing.download_label")),
            translation_tab: gr.update(label=t("translation.tab_title")),
            trans_subtitle_input: gr.update(label=t("translation.upload_label")),
            trans_api_accordion: gr.update(label=t("llm.api_accordion")),
            trans_api_key_input: gr.update(label=t("llm.api_key_label")),
            trans_base_url_input: gr.update(label=t("llm.base_url_label")),
            trans_model_name_input: gr.update(label=t("llm.model_name_label")),
            trans_proxy_input: gr.update(label=t("llm.proxy_label"), placeholder=t("llm.proxy_placeholder")),
            trans_concurrency_slider: gr.update(label=t("llm.concurrency_label"), info=t("llm.concurrency_info")),
            trans_chunk_size_slider: gr.update(
                label=t("translation.chunk_size_label"), info=t("translation.chunk_size_info")
            ),
            trans_options_accordion: gr.update(label=t("translation.options_accordion")),
            target_language_dropdown: gr.update(label=t("translation.target_lang_label")),
            double_language_checkbox: gr.update(label=t("translation.bilingual_label")),
            translation_button: gr.update(value=t("translation.start_button")),
            trans_status_msg: gr.update(label=t("translation.status_label")),
            translation_file_output: gr.update(label=t("translation.download_label")),
            translation_preview: gr.update(label=t("translation.preview_label")),
            ai_segmentation_tab: gr.update(label=t("segmentation.tab_title")),
            seg_description_md: gr.update(value=t("segmentation.description")),
            seg_file_input: gr.update(label=t("segmentation.upload_label")),
            seg_submit_btn: gr.update(value=t("segmentation.start_button")),
            seg_api_accordion: gr.update(label=t("llm.api_accordion")),
            seg_api_key_input: gr.update(label=t("llm.api_key_label")),
            seg_base_url_input: gr.update(label=t("llm.base_url_label")),
            seg_model_name_input: gr.update(label=t("llm.model_name_label")),
            seg_proxy_input: gr.update(label=t("llm.proxy_label"), placeholder=t("llm.proxy_placeholder")),
            seg_concurrency_slider: gr.update(label=t("llm.concurrency_label"), info=t("llm.concurrency_info")),
            seg_chunk_size_slider: gr.update(
                label=t("segmentation.chunk_size_label"), info=t("segmentation.chunk_info")
            ),
            seg_status: gr.update(label=t("segmentation.status_label")),
            seg_file_output: gr.update(label=t("segmentation.download_label")),
            tips_title_md: gr.update(value=t("ui.tips_title")),
            tips_content_md: gr.update(value=t("ui.tips_content")),
            ui_warning_cpu_md: gr.update(value=t("ui.warning_cpu")),
            ui_info_gpu_available_md: gr.update(value=t("ui.info_gpu_available")),
            ui_warning_no_gpu_md: gr.update(value=t("ui.warning_no_gpu")),
            word_format_checkboxes: gr.update(label=t("output.word_level_label"), info=t("output.word_level_info")),
            enable_split_checkbox: gr.update(label=t("output.enable_split_label")),
            max_line_width_slider: gr.update(label=t("output.max_width_label"), info=t("output.max_width_info")),
            output_config_accordion: gr.update(label=t("output.accordion_title")),
            tab_format: gr.update(label=t("output.tab_format")),
            tab_word_level: gr.update(label=t("output.tab_word_level")),
            tab_split: gr.update(label=t("output.tab_split")),
        }

    # --- 构建UI界面 ---
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        title_md = gr.Markdown(t("app.title"))

        with gr.Row():
            with gr.Column(scale=1):
                language_dropdown = gr.Dropdown(
                    choices=[
                        ("中文", "zh"),
                        ("English", "en"),
                        ("日本語", "ja"),
                        ("한국어", "ko"),
                    ],
                    value=saved_language,
                    label="Language / 语言",
                    interactive=True,
                )

        app_description = gr.Markdown(t("app.description"))

        with gr.Accordion(t("model.settings_title"), open=True) as model_settings_title:
            model_cloud_section_title = gr.Markdown(t("model.cloud_section_title"))
            cloud_model_dropdown = gr.Dropdown(
                choices=list(AVAILABLE_MODELS.keys()),
                value=saved_cloud_model,
                label=t("model.cloud_model_label"),
                info=t("model.cloud_model_info"),
                interactive=True,
            )

            def update_model_description(model_name: str) -> str:
                """根据选定的模型名称获取其描述。

                Args:
                    model_name (str): 模型名称。

                Returns:
                    str: 模型能力描述。
                """
                return AVAILABLE_MODELS.get(model_name, "")

            model_description = gr.Textbox(
                label=t("model.model_description_label"),
                value=AVAILABLE_MODELS.get(saved_cloud_model, ""),
                interactive=False,
                lines=1,
            )

            cloud_model_dropdown.change(
                fn=update_model_description,
                inputs=[cloud_model_dropdown],
                outputs=[model_description],
            )

            load_cloud_model_button = gr.Button(t("model.load_cloud_button"), variant="primary", size="lg")

            gr.Markdown("---")
            model_local_section_title = gr.Markdown(t("model.local_section_title"))

            with gr.Row():
                with gr.Column(scale=3):
                    local_model_path_input = gr.Textbox(
                        label=t("model.local_path_label"),
                        placeholder=t("model.local_path_placeholder"),
                        value=saved_model_path if saved_model_path is not None else "",
                    )
                with gr.Column(scale=1, min_width=150):
                    load_local_model_button = gr.Button(t("model.load_local_button"), variant="secondary")

            model_status_output = gr.Textbox(
                label=t("model.status_label"),
                value=initial_model_status,
                lines=2,
                interactive=False,
                max_lines=3,
            )

            chunk_slider = gr.Slider(
                minimum=CHUNK_SLIDER_MIN,
                maximum=CHUNK_SLIDER_MAX,
                value=initial_chunk_length,
                step=CHUNK_SLIDER_STEP,
                label=t("model.chunk_length_label"),
                info=t("model.chunk_length_info"),
            )

        gr.Markdown("---")
        # --- 字幕生成 Tab ---
        with gr.Tab(t("transcription.tab_title")) as transcription_tab:
            video_input = gr.File(
                label=t("transcription.upload_label"),
                file_count="multiple",
            )

            # --- 输出配置区域---
            with gr.Accordion(t("output.accordion_title"), open=True) as output_config_accordion:
                # --- Tab 1: 基础格式 ---
                with gr.Tab(t("output.tab_format")) as tab_format:
                    format_checkboxes = gr.CheckboxGroup(
                        choices=["srt", "vtt", "txt", "json", "lrc", "ass"],
                        value=["srt"],
                        label=t("transcription.format_label"),
                        interactive=True,
                    )

                # --- Tab 2: 逐字/逐词格式 ---
                with gr.Tab(t("output.tab_word_level")) as tab_word_level:
                    word_format_checkboxes = gr.CheckboxGroup(
                        choices=[("word_srt", "word_srt"), ("char_srt", "char_srt")],
                        label=t("output.word_level_label"),
                        info=t("output.word_level_info"),
                        interactive=True,
                    )

                # --- Tab 3: 长度限制 ---
                with gr.Tab(t("output.tab_split")) as tab_split:
                    enable_split_checkbox = gr.Checkbox(label=t("output.enable_split_label"), value=False)

                    max_line_width_slider = gr.Slider(
                        minimum=MAX_LINE_WIDTH_MIN,
                        maximum=MAX_LINE_WIDTH_MAX,
                        value=MAX_LINE_WIDTH_DEFAULT,
                        step=MAX_LINE_WIDTH_STEP,
                        label=t("output.max_width_label"),
                        info=t("output.max_width_info"),
                    )

                with gr.Tab(t("diarization.tab_title")) as speaker_diarization_tab:
                    enable_speaker_diarization_checkbox = gr.Checkbox(
                        label=t("diarization.enable_label"),
                        info=t("diarization.enable_info"),
                        value=False,
                    )
                    diarization_dev_msg = gr.Markdown(t("diarization.development_msg"))

            media_submit_button = gr.Button(t("transcription.submit_button"), variant="primary", size="lg")

            status_output = gr.Textbox(label=t("transcription.status_label"), lines=1, interactive=False)
            with gr.Accordion(t("transcription.result_title"), open=True) as subtitle_result_accordion:
                subtitle_file_output = gr.File(
                    label=t("transcription.download_label"),
                    interactive=False,
                    file_count="multiple",
                )

                subtitle_zip_download_button = gr.Button(t("transcription.zip_button"), variant="secondary")

                subtitle_zip_output = gr.File(
                    label="ZIP Archive",
                    interactive=False,
                    file_count="single",
                    scale=3,
                    height=100,
                )

                subtitle_preview_output = gr.Textbox(
                    label=t("transcription.preview_label"),
                    lines=10,
                    max_lines=20,
                    interactive=False,
                )

                subtitle_zip_download_button.click(
                    fn=app.transcription_controller.create_zip_archive,
                    inputs=[subtitle_file_output],
                    outputs=[subtitle_zip_output],
                )

        # --- 字幕编辑 Tab ---
        with gr.Tab(t("editing.tab_title")) as subtitle_editing_tab:
            subtitle_to_edit_input = gr.File(label=t("editing.upload_label"), file_count="multiple")

            saved_corrections = app.subtitle_editor_controller.load_corrections()

            correction_table = gr.Dataframe(
                headers=[t("editing.table_header_error"), t("editing.table_header_correct")],
                datatype=["str", "str"],
                value=saved_corrections,
                interactive=True,
                label=t("editing.correction_table_label"),
                wrap=True,
            )

            with gr.Row():
                apply_correction_btn = gr.Button(t("editing.batch_replace_btn"), variant="primary")
                save_correction_btn = gr.Button(t("editing.save_correction_btn"), variant="secondary")

            editing_tips_md = gr.Markdown(t("editing.tips"))

            subtitle_editor_df = gr.Dataframe(
                headers=[
                    t("editing.col_id"),
                    t("editing.col_start"),
                    t("editing.col_end"),
                    t("editing.col_text"),
                ],
                datatype=["number", "str", "str", "str"],
                interactive=True,
                wrap=True,
                label=t("editing.data_label"),
            )

            save_edit_button = gr.Button(t("editing.save_subtitle_btn"), variant="primary")

            edited_file_output = gr.File(label=t("editing.download_label"), interactive=False)

            # --- 字幕编辑逻辑 ---
            def on_file_upload(files: list[Any]) -> list[list[Any]] | None:
                """处理字幕文件上传并加载为表格数据。

                Args:
                    files (list[Any]): 上传的文件列表。

                Returns:
                    list[list[Any]] | None: 解析后的表格二维数据。
                """
                if not files:
                    return None
                df_data, _status = app.subtitle_editor_controller.load_subtitle_file(files)
                return df_data

            subtitle_to_edit_input.change(
                fn=on_file_upload,
                inputs=[subtitle_to_edit_input],
                outputs=[subtitle_editor_df],
            )

            save_edit_button.click(
                fn=app.subtitle_editor_controller.save_subtitles,
                inputs=[subtitle_editor_df, subtitle_to_edit_input],
                outputs=[edited_file_output],
            )

            save_correction_btn.click(
                fn=app.subtitle_editor_controller.save_corrections,
                inputs=[correction_table],
                outputs=[],
            ).then(lambda: gr.Info(t("editing.save_success_info")))

            apply_correction_btn.click(
                fn=app.subtitle_editor_controller.apply_batch_corrections,
                inputs=[subtitle_editor_df, correction_table],
                outputs=[subtitle_editor_df],
            )

        # AI 翻译 Tab
        with gr.Tab(t("translation.tab_title")) as translation_tab:
            trans_subtitle_input = gr.File(label=t("translation.upload_label"), file_count="multiple")

            with gr.Accordion(t("llm.api_accordion"), open=True) as trans_api_accordion:
                with gr.Row():
                    trans_api_key_input = gr.Textbox(
                        label=t("llm.api_key_label"),
                        type="password",
                        placeholder="sk-...",
                        value=saved_api_key,
                    )
                    trans_base_url_input = gr.Textbox(label=t("llm.base_url_label"), value=saved_base_url)
                with gr.Row():
                    trans_model_name_input = gr.Textbox(label=t("llm.model_name_label"), value=saved_llm_model)
                    trans_proxy_input = gr.Textbox(
                        label=t("llm.proxy_label"),
                        placeholder=t("llm.proxy_placeholder"),
                        value=saved_proxy,
                    )
                with gr.Row():
                    trans_concurrency_slider = gr.Slider(
                        minimum=LLM_CONCURRENCY_MIN,
                        maximum=LLM_CONCURRENCY_MAX,
                        value=LLM_CONCURRENCY_DEFAULT,
                        step=LLM_CONCURRENCY_STEP,
                        label=t("llm.concurrency_label"),
                        info=t("llm.concurrency_info"),
                    )
                    trans_chunk_size_slider = gr.Slider(
                        minimum=LLM_CHUNK_SIZE_MIN,
                        maximum=LLM_CHUNK_SIZE_MAX,
                        value=LLM_CHUNK_SIZE_DEFAULT,
                        step=LLM_CHUNK_SIZE_STEP,
                        label=t("translation.chunk_size_label"),
                        info=t("translation.chunk_size_info"),
                    )

            with gr.Accordion(t("translation.options_accordion"), open=True) as trans_options_accordion:
                with gr.Row():
                    target_language_dropdown = gr.Dropdown(
                        choices=[
                            ("中文", "Chinese"),
                            ("English", "English"),
                            ("日本語", "Japanese"),
                            ("한국어", "Korean"),
                        ],
                        value="Chinese",
                        label=t("translation.target_lang_label"),
                    )
                    double_language_checkbox = gr.Checkbox(label=t("translation.bilingual_label"), value=True)

            translation_button = gr.Button(t("translation.start_button"), variant="primary", size="lg")

            trans_status_msg = gr.Textbox(label=t("translation.status_label"), interactive=False)
            translation_file_output = gr.File(
                label=t("translation.download_label"), interactive=False, file_count="multiple"
            )
            translation_preview = gr.Textbox(label=t("translation.preview_label"), lines=10, interactive=False)

            # 事件绑定
            translation_button.click(
                fn=app.translation_controller.handle_translation,
                inputs=[
                    trans_subtitle_input,
                    target_language_dropdown,
                    double_language_checkbox,
                    trans_api_key_input,
                    trans_base_url_input,
                    trans_model_name_input,
                    trans_proxy_input,
                    trans_concurrency_slider,
                    trans_chunk_size_slider,
                ],
                outputs=[trans_status_msg, translation_file_output, translation_preview],
            )

        # -- AI 断句 Tab ---
        with gr.Tab(t("segmentation.tab_title")) as ai_segmentation_tab:
            seg_description_md = gr.Markdown(t("segmentation.description"))

            seg_file_input = gr.File(label=t("segmentation.upload_label"), file_count="multiple")
            seg_submit_btn = gr.Button(t("segmentation.start_button"), variant="primary")

            with gr.Accordion(t("llm.api_accordion"), open=True) as seg_api_accordion:
                with gr.Row():
                    seg_api_key_input = gr.Textbox(
                        label=t("llm.api_key_label"),
                        type="password",
                        placeholder="sk-...",
                        value=saved_api_key,
                    )
                    seg_base_url_input = gr.Textbox(label=t("llm.base_url_label"), value=saved_base_url)
                with gr.Row():
                    seg_model_name_input = gr.Textbox(label=t("llm.model_name_label"), value=saved_llm_model)
                    seg_proxy_input = gr.Textbox(
                        label=t("llm.proxy_label"),
                        placeholder=t("llm.proxy_placeholder"),
                        value=saved_proxy,
                    )
                with gr.Row():
                    seg_concurrency_slider = gr.Slider(
                        minimum=LLM_CONCURRENCY_MIN,
                        maximum=LLM_CONCURRENCY_MAX,
                        value=LLM_CONCURRENCY_DEFAULT,
                        step=LLM_CONCURRENCY_STEP,
                        label=t("llm.concurrency_label"),
                        info=t("llm.concurrency_info"),
                    )
                    seg_chunk_size_slider = gr.Slider(
                        minimum=LLM_CHUNK_SIZE_MIN,
                        maximum=LLM_CHUNK_SIZE_MAX,
                        value=LLM_CHUNK_SIZE_DEFAULT,
                        step=LLM_CHUNK_SIZE_STEP,
                        label=t("segmentation.chunk_size_label"),
                        info=t("segmentation.chunk_info"),
                    )

            seg_status = gr.Textbox(label=t("segmentation.status_label"), interactive=False)
            seg_file_output = gr.File(label=t("segmentation.download_label"), file_count="multiple")

            seg_submit_btn.click(
                fn=app.translation_controller.handle_ai_segmentation,
                inputs=[
                    seg_file_input,
                    seg_api_key_input,
                    seg_base_url_input,
                    seg_model_name_input,
                    seg_proxy_input,
                    seg_concurrency_slider,
                    seg_chunk_size_slider,
                ],
                outputs=[seg_status, seg_file_output],
            )

        # --- 事件监听器 ---
        load_local_model_button.click(
            fn=app.model_controller.handle_load_local_click,
            inputs=[local_model_path_input, chunk_slider, cloud_model_dropdown],
            outputs=[model_status_output],
        )
        load_cloud_model_button.click(
            fn=app.model_controller.handle_load_cloud_click,
            inputs=[chunk_slider, cloud_model_dropdown],
            outputs=[model_status_output],
        )

        media_submit_button.click(
            fn=app.transcription_controller.process_media,
            inputs=[
                video_input,
                chunk_slider,
                format_checkboxes,
                word_format_checkboxes,
                enable_split_checkbox,
                max_line_width_slider,
            ],
            outputs=[status_output, subtitle_file_output, subtitle_preview_output],
        )

        gr.Markdown("---")
        tips_title_md = gr.Markdown(t("ui.tips_title"))
        tips_content_md = gr.Markdown(t("ui.tips_content"))

        ui_warning_cpu_md = gr.Markdown(visible=False)
        ui_info_gpu_available_md = gr.Markdown(visible=False)
        ui_warning_no_gpu_md = gr.Markdown(visible=False)

        # --- 设备状态显示 (国际化) ---
        device = app.asr_service.device
        if device and hasattr(device, "type") and device.type == "cpu":
            ui_warning_cpu_md = gr.Markdown(t("ui.warning_cpu"), visible=True)
        elif device and torch.cuda.is_available():
            ui_info_gpu_available_md = gr.Markdown(t("ui.info_gpu_available"), visible=True)
        else:
            ui_warning_no_gpu_md = gr.Markdown(t("ui.warning_no_gpu"), visible=True)

        # --- 语言切换事件监听器 ---
        all_ui_outputs = [
            title_md,
            app_description,
            model_settings_title,
            model_cloud_section_title,
            cloud_model_dropdown,
            model_description,
            load_cloud_model_button,
            model_local_section_title,
            local_model_path_input,
            load_local_model_button,
            model_status_output,
            chunk_slider,
            transcription_tab,
            video_input,
            media_submit_button,
            status_output,
            subtitle_result_accordion,
            subtitle_file_output,
            subtitle_zip_download_button,
            subtitle_preview_output,
            tips_title_md,
            tips_content_md,
            ui_warning_cpu_md,
            ui_info_gpu_available_md,
            ui_warning_no_gpu_md,
            format_checkboxes,
            word_format_checkboxes,
            enable_split_checkbox,
            max_line_width_slider,
            output_config_accordion,
            tab_format,
            tab_word_level,
            tab_split,
            speaker_diarization_tab,
            enable_speaker_diarization_checkbox,
            diarization_dev_msg,
            subtitle_editing_tab,
            subtitle_to_edit_input,
            correction_table,
            apply_correction_btn,
            save_correction_btn,
            editing_tips_md,
            subtitle_editor_df,
            save_edit_button,
            edited_file_output,
            translation_tab,
            trans_subtitle_input,
            trans_api_accordion,
            trans_api_key_input,
            trans_base_url_input,
            trans_model_name_input,
            trans_proxy_input,
            trans_concurrency_slider,
            trans_chunk_size_slider,
            trans_options_accordion,
            target_language_dropdown,
            double_language_checkbox,
            translation_button,
            trans_status_msg,
            translation_file_output,
            translation_preview,
            ai_segmentation_tab,
            seg_description_md,
            seg_file_input,
            seg_submit_btn,
            seg_api_accordion,
            seg_api_key_input,
            seg_base_url_input,
            seg_model_name_input,
            seg_proxy_input,
            seg_concurrency_slider,
            seg_chunk_size_slider,
            seg_status,
            seg_file_output,
        ]

        language_dropdown.change(
            fn=change_language,
            inputs=[language_dropdown],
            outputs=all_ui_outputs,
        )

    return demo
