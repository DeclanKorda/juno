import time
import prompts
import llama_cpp
from llama_cpp.llama_types import ChatCompletionMessage
import datetime
from rich import color
from rich.console import Console

import chromadb
from chromadb.config import Settings
from prompts import *
import re


client = chromadb.PersistentClient(settings=Settings(allow_reset=True,
                                                     anonymized_telemetry=False),
                                           path="knowledgebase")

if input('RESET DATABASE Y/N') == 'Y':
    client.reset()
semantic = client.get_or_create_collection(name='semantic')
layer_1 = client.get_or_create_collection(name='layer_1')
layer_2 = client.get_or_create_collection(name='layer_2')
layer_3 = client.get_or_create_collection(name='layer_3')
console = Console(color_system='256')

class LLM:
    def __init__(self, model_path='', n_ctx=4096, verbose=False, max_tokens=250, bot_tag="Bot"):

        self.model = llama_cpp.Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=2,
            n_batch=512,
            f16_kv=True,
            verbose=verbose
            )

        self.bot_tag = bot_tag
        self.max_tokens = max_tokens
        self.immediate_history = ['']


    def add_message(self, content: str):
        """
        Writes a message and bot response to memory

        returns string
        """
        time_stamp = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')

        self.update_personal_memory(time_stamp, content)

    def update_personal_memory(self, time_stamp, content, layer1_limit=1000, layer2_limit=10000):
        """updates personal memory. Restructures data if layer_1 is full."""
        layer_1.add(ids=[time_stamp], metadatas=[{'date': time_stamp}], documents=content)



        temp = ''
        chat_history = layer_1.get(include=['metadatas', 'documents'])
        for i in range(0, len(chat_history['documents'])):
            temp += f'{chat_history["metadatas"][i]["date"]}: {chat_history["documents"][i]}\n'
        if len(self.model.tokenize(temp.encode('utf-8'))) > layer1_limit:
            console.print('[orange3]layer_1 full! summarizing and moving to layer 2')
            summary = self.summarize_chat(temp)
            console.print(summary, style='blue')

            """n = 500
            m = 50
            chunks: str = [summary[i:i+n] for i in range(0, len(summary), n-m)]"""
            lines = summary.split('\n')
            header_indexes = [0]
            for i in range(0, len(lines)):
                lines[i] += '\n' # add back in the newline char
                if ':' in lines[i]:
                    # line is a header
                    header_indexes.append(i)
            chunks = []
            for i in range(0, len(header_indexes)-1):
                chunks.append(''.join(lines[header_indexes[i]: header_indexes[i+1]]))
            chunks.append(''.join(lines[header_indexes[-1]:]))
            console.print('[orange3] summarization split!')
            console.print(chunks, style='cyan3')

            layer_2.add(ids=[str(i) + datetime.datetime.now().strftime('%d-%m-%Y %H:%M') for i in range(0, len(chunks))],
                        metadatas=[{'date': datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
                                   for i in range(0, len(chunks))],
                        documents=chunks)

            layer_1.delete(ids=chat_history['ids'])
    def retrieve_memories(self):
        """returns relevant text from semantic and personal memory."""

        layer1_query = layer_1.query(query_texts=self.immediate_history, include=['metadatas', 'documents'], n_results=3)
        layer2_query = layer_2.query(query_texts=self.immediate_history, include=['metadatas', 'documents'], n_results=5)
        # semantic_query = semantic.query(query_texts=self.immediate_history, include=['metadatas', 'documents'],
        # n_results=2)[0]
        if len(layer1_query['metadatas'][0]) == 0:
            chats = ''
        else:
            chats = ''.join(f'[{layer1_query["metadatas"][0][i]["date"]}]:\n{layer1_query["documents"][0][i]}\n'
                            for i in range(0, len(layer1_query['documents'][0])))
            for x in self.immediate_history:
                chats = chats.replace(x, '')
        if len(layer2_query['metadatas'][0]) == 0:
            memories=''
        else:
            memories = ''.join(
                f'[{layer2_query["metadatas"][0][i]["date"]}]: {layer2_query["documents"][0][i]}\n'
                for i in range(0, len(layer2_query['documents'][0])))
        semantic_knowledge = ''
        return {'chats': chats, 'memories': memories, 'semantic_knowledge': semantic_knowledge}

    def summarize_chat(self, chat):
        console.print(summarize_chat_prompt.format(chat=chat), style='cyan')
        summary = self.model(summarize_chat_prompt.format(chat=chat), max_tokens=750, stop=['ENDSUMMARY'])['choices'][0]['text']
        #console.print(f'[cyan]{summary}')
        return summary
    def send(self, message, tag):


        #self.add_message(message, tag)
        content = f'{tag}: {message}\n'
        history = ''.join(self.immediate_history) + content
        context = self.retrieve_memories()
        console.print('[bold cyan3]Juno[bright_black] >>[white]\n')
        response = ' '
        char_in_line = 0
        prompt = juno_prompt.format(semantic=context['semantic_knowledge'],
                                    memories=context['memories'],
                                    chats=context['chats'],
                                    current_history=history,
                                    tag=tag,
                                    timestamp=datetime.datetime.now().strftime('%d-%m-%Y'))
        if len(self.model.tokenize(prompt.encode('utf-8'))) > 2048:
            console.print('[red3]Warning: token limit exceeded!!')
        console.print(prompt, style='magenta3')

        for token in self.model(prompt,
                                stream=True,
                                max_tokens=self.max_tokens,
                                temperature=0.8,
                                stop=['Juno:', f'{tag}:', 'System:', 'Human:', 'Assistant:', 'USER:', "ASSISTANT:", '[', '</s>', '<e>', '\n\n' ,'Please let me know how you would like to proceed', 'ENDRESPONSE', 'BEGININPUT', 'Note:']
                                ):
            chunk = token['choices'][0]['text']
            response += chunk
            char_in_line += 1
            console.print(chunk, end='')
            if char_in_line > 20:
                console.print('\n', end='')
                char_in_line = 0
        console.print('\n')
        response = f'{self.bot_tag}: {response}\n'
        self.immediate_history.append(content + response)
        if len(self.immediate_history) > 8:
            self.immediate_history.pop(0)

        to_store = content + response
        self.add_message(to_store)


