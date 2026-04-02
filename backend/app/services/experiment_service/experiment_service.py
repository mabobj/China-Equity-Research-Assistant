"""实验管理服务（骨架版）。"""

from __future__ import annotations


class ExperimentService:
    """管理预测/评估相关默认版本。"""

    def __init__(self) -> None:
        self._default_model_version = "baseline-rule-v1"
        self._default_feature_version = "features-v0-baseline"
        self._default_label_version = "labels-v0-forward-return"

    def get_default_model_version(self) -> str:
        return self._default_model_version

    def get_default_feature_version(self) -> str:
        return self._default_feature_version

    def get_default_label_version(self) -> str:
        return self._default_label_version

