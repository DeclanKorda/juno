from rich.prompt import Prompt
from rich.layout import Layout
from rich.panel import Panel
from rich.color import Color
import rich.markup
from llm import *

username = console.input('[bold red3]Enter Name [bright_black]>>\n')
Juno = LLM(model_path='/Users/declankorda/Models/mythical-destroyer-l2-13b.Q4_K_S.gguf',
           bot_tag='Juno',
           verbose=True)
while True:
    to_send = console.input(f'[bold red3]{username}[bright_black] >>\n')
    Juno.send(to_send, username)


