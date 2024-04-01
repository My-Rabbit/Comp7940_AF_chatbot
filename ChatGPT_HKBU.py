import configparser
import datetime
import json
import logging
import requests
from transformers import GPT2Tokenizer

class HKBU_ChatGPT():
    def __init__(self,config_='./config.ini'):
        if type(config_) == str:
            self.config = configparser.ConfigParser()
            self.config.read(config_)
        elif type(config_) == configparser.ConfigParser:
            self.config = config_
        self.conversation = []
        self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

    def generate(self):
        currentMonth = datetime.date.today().month
        currentDay = datetime.date.today().day
        
        message = f'历史中哪些事件发生在{currentMonth}月{currentDay}日？使用英文简单概括，列举两条并发送相关图片。当你想发送一张照片时，请使用Markdown, 并且不要有反斜线, 不要用代码块。使用 Unsplash API 。发送图片时，请使用Markdown，将Unsplash API中的PUT_YOUR_QUERY_HERE替换成描述该事件的一个最重要的单词。'
        conversation = [
            {'role': 'user', 'content': message}
        ]
        url = self.config['CHATGPT']['REDIRECT_URL']
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['CHATGPT']['ACCESS_TOKEN']}"
        }
        model="gpt-4"
        payload = {
            "model": model,
            "messages": conversation, 
            "temperature": 0.9,  # 1.0,
            "top_p": 1.0,  # 1.0,
            "stream": True,
        }
        response = requests.post(url, headers = headers, json = payload, stream=True)
        gpt_replying = self.decode_stream_response(response)
        return gpt_replying
    
    def submit(self, message):   
        self.conversation.append({"role": "user", "content": message}) 
        self._limit_tokens()

        url = self.config['CHATGPT']['REDIRECT_URL']
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['CHATGPT']['ACCESS_TOKEN']}"
        }
        model="gpt-4"
        payload = {
            "model": model,
            "messages": self.conversation, 
            "temperature": 0.9,
            "top_p": 1.0, 
            "stream": True,
        }
        response = requests.post(url, headers = headers, json = payload, stream=True)
        gpt_replying = self.decode_stream_response(response)
        self.conversation.append({"role": "system", "content": gpt_replying}) 
        return gpt_replying

    def _limit_tokens(self):
        max_tokens = 2048
        tokens = 0
        for message in reversed(self.conversation):
            tokens += len(self.tokenizer.encode(message["content"]))
            if tokens > max_tokens:
                self.conversation.remove(message)
            else:
                break
        
    def decode_chunk(self, chunk):
    # 提前读取一些信息 （用于判断异常）
        chunk_decoded = chunk.decode()
        chunkjson = None
        has_choices = False
        choice_valid = False
        has_content = False
        has_role = False
        try: 
            chunkjson = json.loads(chunk_decoded[6:])
            has_choices = 'choices' in chunkjson
            if has_choices: choice_valid = (len(chunkjson['choices']) > 0)
            if has_choices and choice_valid: has_content = ("content" in chunkjson['choices'][0]["delta"])
            if has_content: has_content = (chunkjson['choices'][0]["delta"]["content"] is not None)
            if has_choices and choice_valid: has_role = "role" in chunkjson['choices'][0]["delta"]
        except: 
            pass
        return chunk_decoded, chunkjson, has_choices, choice_valid, has_content, has_role
    
    def decode_stream_response(self, response):   
        stream_response =  response.iter_lines()

        gpt_replying_buffer = ""
        is_head_of_the_stream = True

        stream_response =  response.iter_lines()
        if response.status_code == 200:
            while True:
                try:
                    chunk = next(stream_response)
                except StopIteration:
                # 非OpenAI官方接口的出现这样的报错，OpenAI和API2D不会走这里
                    chunk_decoded = chunk.decode()
                    error_msg = chunk_decoded
                chunk_decoded, chunkjson, has_choices, choice_valid, has_content, has_role = self.decode_chunk(chunk)

                if is_head_of_the_stream and (r'"object":"error"' not in chunk_decoded) and (r"content" not in chunk_decoded):
                # 数据流的第一帧不携带content
                    is_head_of_the_stream = False; continue
                if chunk:
                    try:
                        if has_choices and not choice_valid:
                        # 一些垃圾第三方接口的出现这样的错误
                            continue
                    # 前者是API2D的结束条件，后者是OPENAI的结束条件
                        if ('data: [DONE]' in chunk_decoded) or (len(chunkjson['choices'][0]["delta"]) == 0):
                        # 判定为数据流的结束，gpt_replying_buffer也写完了
                            logging.info(f'[response] {gpt_replying_buffer}')
                            break
                    # 处理数据流的主体
                        status_text = f"finish_reason: {chunkjson['choices'][0].get('finish_reason', 'null')}"
                    # 如果这里抛出异常，一般是文本过长，详情见get_full_error的输出
                        if has_content:
                        # 正常情况
                            gpt_replying_buffer = gpt_replying_buffer + chunkjson['choices'][0]["delta"]["content"]
                        elif has_role:
                            continue
                        else:
                            gpt_replying_buffer = gpt_replying_buffer + chunkjson['choices'][0]["delta"]["content"]
                
                    except Exception as e:
                        print(error_msg)
            
            return gpt_replying_buffer
        else:
            return 'Error:', response


if __name__ == '__main__':
    ChatGPT_test = HKBU_ChatGPT()

    while True:
        
        user_input = input("Typing anything to ChatGPT:\t")
        response = ChatGPT_test.submit(user_input)
        print(response)

