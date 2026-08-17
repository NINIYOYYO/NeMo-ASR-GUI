"""模型加载与配置控制模块。

处理本地模型与 NVIDIA NGC 云端模型的加载、释放及配置持久化事件。
"""

from interfaces import IASRService, IConfigManager, IModelController
from utils.exceptions import ModelLoadError


class ModelController(IModelController):
    """专门处理模型相关 UI 事件的控制器。"""

    def __init__(self, app_services: IASRService, config: IConfigManager) -> None:
        """初始化模型控制器。

        Args:
            app_services (IASRService): ASR 语音识别服务接口实例。
            config (IConfigManager): 配置管理器接口实例。
        """
        self.services: IASRService = app_services
        self.config: IConfigManager = config

    def handle_load_local_click(
        self,
        path_from_input_box: str,
        chunk_val_from_slider: int,
        selected_cloud_model: str,
    ) -> str:
        """处理“加载本地模型”按钮点击事件。

        Args:
            path_from_input_box (str): 本地 .nemo 模型文件路径。
            chunk_val_from_slider (int): 滑块选定的音频分块长度（秒）。
            selected_cloud_model (str): 当前下拉框选定的云端模型名称。

        Returns:
            str: 模型加载操作的状态消息。

        Raises:
            ModelLoadError: 当模型加载失败时抛出。
        """
        try:
            if not path_from_input_box or not path_from_input_box.strip():
                return "错误：请输入有效的本地模型路径后点击\"加载本地模型\"。若要加载云端模型，请使用对应按钮。"
            status = self.services.load_model_from_local(path_from_input_box)
            if self.services.is_model_loaded:
                self.config.save_config(
                    local_model_path=path_from_input_box,
                    chunk_length_s=chunk_val_from_slider,
                    cloud_model_name=selected_cloud_model,
                )
            return status
        except Exception as e:
            raise ModelLoadError(f"加载本地模型时出错: {e}") from e

    def handle_load_cloud_click(
        self,
        chunk_val_from_slider: int,
        selected_cloud_model: str,
    ) -> str:
        """处理“加载云端模型”按钮点击事件。

        Args:
            chunk_val_from_slider (int): 滑块选定的音频分块长度（秒）。
            selected_cloud_model (str): 选定的 NGC 云端模型标识符。

        Returns:
            str: 模型加载操作的状态消息。

        Raises:
            ModelLoadError: 当模型加载失败时抛出。
        """
        try:
            status = self.services.load_model_from_ngc(selected_cloud_model)
            if self.services.is_model_loaded:
                self.config.save_config(
                    local_model_path="",
                    chunk_length_s=chunk_val_from_slider,
                    cloud_model_name=selected_cloud_model,
                )
            return status
        except Exception as e:
            raise ModelLoadError(f"加载云端模型时出错: {e}") from e
