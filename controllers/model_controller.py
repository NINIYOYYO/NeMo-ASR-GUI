
from interfaces import IASRService, IConfigManager, IModelController
from utils.exceptions import ModelLoadError


class ModelController(IModelController):
    """
    一个专门处理模型相关 UI 事件的控制器

    """

    def __init__(self, app_services: IASRService, config: IConfigManager) -> None:
        # 控制器持有对主 app 实例的引用，以便访问核心服务
         self.services = app_services
         self.config = config

    # --- 按钮点击处理程序 ---
    def handle_load_local_click(self, path_from_input_box, chunk_val_from_slider, selected_cloud_model):
        """处理“加载本地模型”按钮点击事件。"""

        try:
            if not path_from_input_box or not path_from_input_box.strip():
                return "错误：请输入有效的本地模型路径后点击\"加载本地模型\"。若要加载云端模型，请使用对应按钮。"
            status = self.services.load_model_from_local(path_from_input_box)
            if self.services.is_model_loaded:
                self.config.save_config(
                    local_model_path=path_from_input_box, chunk_length_s=chunk_val_from_slider, cloud_model_name=selected_cloud_model)
            return status
        except Exception as e:
            raise ModelLoadError(f"加载本地模型时出错: {e}") from e

    def handle_load_cloud_click(self, chunk_val_from_slider, selected_cloud_model):
        """处理“加载云端模型”按钮点击事件。"""
        try:

            status = self.services.load_model_from_ngc(selected_cloud_model)
            if self.services.is_model_loaded:
                self.config.save_config(local_model_path="", chunk_length_s=chunk_val_from_slider, cloud_model_name=selected_cloud_model)
            return status
        
        except Exception as e:
            raise ModelLoadError(f"加载云端模型时出错: {e}") from e





