

class LastZBotError(Exception):
    pass


class CaptureError(LastZBotError):
    pass


class ClickerError(LastZBotError):
    pass


class OCRError(LastZBotError):
    pass


class ConfigError(LastZBotError):
    pass


class MacroStepError(LastZBotError):

    def __init__(self, step_label: str, message: str) -> None:
        self.step_label = step_label
        self.message = message
        super().__init__(f"[{step_label}] {message}")


class AntiSleepError(LastZBotError):
    pass
