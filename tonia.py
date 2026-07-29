import os

class Color:
    class Foreground:
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        MAGENTA = "\033[35m"
        CYAN = "\033[36m"
        WHITE = "\033[37m"
        RESET = "\033[39m"
        def rgb(r, g, b): 
            return f"\033[38;2;{r};{g};{b}m"
    class Background:
        RED = "\033[41m"
        GREEN = "\033[42m"
        YELLOW = "\033[43m"
        BLUE = "\033[44m"
        MAGENTA = "\033[45m"
        CYAN = "\033[46m"
        WHITE = "\033[47m"
        RESET = "\033[49m"
        def rgb(r, g, b): 
            return f"\033[48;2;{r};{g};{b}m"
class PrettyLogger:
    @staticmethod
    def write(message, prefix, prefix_color=Color.Foreground.RESET, printer=print):
        screen_width = os.get_terminal_size().columns
        prefix_length = len(prefix) + 1
        available_space = screen_width - prefix_length
        message_lines = []
        for raw_line in message.split("\n"):
            if raw_line == "":
                message_lines.append("")
                continue
            remaining = raw_line
            while remaining:
                if len(remaining) <= available_space:
                    message_lines.append(remaining)
                    break
                split_index = remaining.rfind(' ', 0, available_space)
                if split_index <= 0:
                    split_index = available_space
                message_lines.append(remaining[:split_index])
                remaining = remaining[split_index:].lstrip()
        for i, line in enumerate(message_lines):
            if i == 0:
                printer(f"{prefix_color}{prefix}{Color.Foreground.RESET} {line}")
            else:
                printer(f"{' ' * prefix_length}{line}")

    def fit(message, size=None, side="left", printer=print):
        if size is None:
            size = os.get_terminal_size().columns
        output_lines = []
        for raw_line in message.split("\n"):
            if raw_line == "":
                output_lines.append("")
                continue
            remaining = raw_line
            while remaining:
                if len(remaining) <= size:
                    output_lines.append(remaining)
                    break
                split_index = remaining.rfind(' ', 0, size)
                if split_index <= 0:
                    split_index = size
                output_lines.append(remaining[:split_index])
                remaining = remaining[split_index:].lstrip()
        text = ''
        for line in output_lines:
            if side == "left":
                text += f"{line}\n"
            elif side == "right":
                text += f"{line:>{size}}\n"
            elif side == "center":
                text += f"{line:^{size}}\n"
            else:
                text += f"{line}\n"
        printer(text)

    def error(message):
        PrettyLogger.write(message, "[ERROR]", Color.Foreground.RED)
    def warning(message):
        PrettyLogger.write(message, "[WARNING]", Color.Foreground.YELLOW)
    def info(message):
        PrettyLogger.write(message, "[INFO]", Color.Foreground.CYAN)
def clear():
    os.system("cls" if os.name == "nt" else "clear")