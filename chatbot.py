import datetime
import logging
import configparser
import re
import json
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

from transformers import GPT2Tokenizer

from ChatGPT_HKBU import HKBU_ChatGPT
from weather import get_weather
from youtube_transcript_api import YouTubeTranscriptApi

import redis



global redis1
def main():
    # Load your token and create an Updater for your Bot
    config = configparser.ConfigParser()
    config.read('config.ini')
    updater = Updater(token=(config['TELEGRAM']['ACCESS_TOKEN']), use_context=True)
    dispatcher = updater.dispatcher
    global redis1
    redis1 = redis.Redis(host=(config['REDIS']['HOST']), password=(config['REDIS']['PASSWORD']), port=(config['REDIS']['REDISPORT']))
   
    # You can set this logging module, so you will know when and why things do not work as expected Meanwhile, update your config.ini as:
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    

    # dispatcher for chatgpt
    global chatgpt
    chatgpt = HKBU_ChatGPT(config)
    chatgpt_handler = MessageHandler(Filters.text & (~Filters.command), equiped_chatgpt)
    dispatcher.add_handler(chatgpt_handler)

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("add", add))############################################用于在redis中添加加一些对(为了方便直接操控)
    dispatcher.add_handler(CommandHandler("help", help_command))##################################用于提示本bot有什么功能
    dispatcher.add_handler(CommandHandler("subscribe", subscribe))##################################用于让用户订阅本BOT,记录其账号到redis中
    dispatcher.add_handler(CommandHandler("setname", set_name))###################################让用户给自己起名，用于展示
    dispatcher.add_handler(CommandHandler("unsubscribe", unsubscribe))###################################用户可以退订本BOT，redis中删除其账号记录
    dispatcher.add_handler(CommandHandler("showsubscribers", showSubscribers))#######################用于展示所有的订阅者和名字
    dispatcher.add_handler(CommandHandler("showall", showAllData))##################################用于检查redis中储存了什么,方便查看
    dispatcher.add_handler(CommandHandler("video1", get_transcript))##################################可以查看一个yutube视频的字幕，前提是此视频有字幕
    dispatcher.add_handler(CommandHandler("video2", get_transcript2))#################################让GPT为你介绍此yutube视频中的内容，由字幕生成
    dispatcher.add_handler(CommandHandler("broadcast",broadcast_subscribers))##########################向所有订阅用户发送一条你写的信息
    dispatcher.add_handler(CommandHandler("post", broadcast_last_reply_to_all_subscribers))################向所有用户分享chatbot的上一条(你的最后一条),GPT聊天,介绍yutube视频,天气播报,货币转换
    dispatcher.add_handler(CommandHandler('weather', weather_command))#############################选择香港某个地区，获得天气播报，并且GPT为你提供建议
    dispatcher.add_handler(CallbackQueryHandler(button))###########################################用于上一个功能显示按钮
    dispatcher.add_handler(CommandHandler("convert", convert))######################################用于计算转换一定量的两种货币
    dispatcher.add_handler(CommandHandler("today", generate_command))##############################用与展示历史上的今天图片与文字


# To start the bot:
    updater.start_polling()
    updater.idle()

def save_message_to_redis(chat_id, message):
    redis_key = f"chat_id_{chat_id}_last_reply"
    redis1.set(redis_key, str(message))


def equiped_chatgpt(update, context): 
    global chatgpt
    reply_message = chatgpt.submit(update.message.text)
    logging.info("Update: " + str(update))
    logging.info("context: " + str(context))
    context.bot.send_message(chat_id=update.effective_chat.id, text=reply_message)
    save_message_to_redis(update.effective_chat.id, reply_message)


def help_command(update: Update, context: CallbackContext) -> None:#########################help命令
    """当用户发送 /help 命令时发送一条消息。"""
    help_message = (
        "您可以使用以下命令：\n"
        "/add - 你想添加的 直接在Redis中添加一些键值对。\n"
        "/help - 显示此消息。\n"
        "/subscribe - 订阅此bot，您的账号将被记录在Redis中。\n"
        "/setname - 你的称呼 为自己设置一个显示名称。\n"
        "/unsubscribe - 从此bot退订，您的账号将从Redis中删除。\n"
        "/showsubscribers - 显示所有订阅者及其名称。\n"
        "/showall - 检查Redis中存储了什么，便于检查。\n"
        "/video1 - 输入一个yutube视频号, 如6EwOQMEwngA 查看指定YouTube视频的字幕（如果有的话）。\n"
        "/video2 - 6EwOQMEwngA 或 https://www.youtube.com/watch?v=6EwOQMEwngA GPT根据其字幕介绍视频内容。\n"
        "/broadcast - 输入内容 向所有订阅用户发送编写的消息。\n"
        "/post - 将chatbot的最后一条回复分享给所有订阅者，包含的功能:GPT聊天,介绍yutube视频,天气播报,货币转换\n"
        "/weather - 获取香港特定地区的天气报告，并且GPT会为您提出建议。\n"
        "/convert -数量 代码1 代码2如(100 CNY HKD) 计算并转换两种货币之间的一定金额。\n"
        "/today - 展示历史上的今天的发生事件和其图片文字。\n"
    )
    
    update.message.reply_text(help_message)


def generate_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    global chatgpt
    
    reply_message = chatgpt.generate()
    update.message.reply_text(reply_message)


def add(update: Update, context: CallbackContext) -> None:######################在redis中添加对
    """Send a message when the command /add is issued."""
    try:
        global redis1
        logging.info(context.args[0])
        msg = context.args[0]   # /add keyword <-- this should store the keyword
        redis1.incr(msg)
        update.message.reply_text('You have said ' + msg +  ' for ' + redis1.get(msg).decode('UTF-8') + ' times.')
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /add <keyword>')

def is_subscriber(chat_id, update):
    """Check if a chat_id is a subscriber and throw an exception if not."""##########用于检查用户是否是订阅者
    chat_id = update.effective_user.id
    if not redis1.sismember('subscribers', chat_id):
        update.message.reply_text('You are not currently subscribed，please subscribe first.')
        raise Exception('Not a subscriber')

def subscribe(update, context):
    """Allow users to subscribe for updates.""" ###########################################订阅
    chat_id = update.effective_chat.id
    try:
        redis1.sadd('subscribers', chat_id)
        update.message.reply_text('You have successfully subscribed!')
    except Exception as e:
        logging.error(f"Error subscribing user: {e}")
        update.message.reply_text('There was an error subscribing you. Please try again later.')

def set_name(update: Update, context: CallbackContext) -> None:########################################让订阅者为自己设定一个名字,其他用户可以看见
    """Allow users to set a custom name."""
    chat_id = update.effective_chat.id
    try:
        # Get the name from the command arguments
        name = ' '.join(context.args)
        is_subscriber(chat_id, update)
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /set_name <name>')
        return

    # Check if the name is not empty
    if not name:
        update.message.reply_text('Name cannot be empty. Please provide a valid name.')
        return

    # Get the chat_id of the user
    chat_id = update.effective_chat.id

    # Create a redis key for the user name
    redis_key = f"chat_id_{chat_id}_name"
    
    try:
        # Save the name to Redis
        redis1.set(redis_key, name)
        update.message.reply_text(f'Your name has been set to {name}!')
    except Exception as e:
        logging.error(f"Error setting name: {e}")
        update.message.reply_text('There was an error setting your name. Please try again later.')

def unsubscribe(update, context):######################################让用户退订
    """Allow users to unsubscribe from updates."""
    chat_id = update.effective_chat.id
    try:
        # This will raise an exception if the user is not a subscriber
        is_subscriber(chat_id, update)
        # If the user is a subscriber, unsubscribe them
        redis1.srem('subscribers', chat_id)
        update.message.reply_text('You have successfully unsubscribed.')
    except Exception as e:
        logging.error(f"Error while unsubscribing user: {e}")
        if str(e) != 'Not a subscriber':
            update.message.reply_text('There was an error unsubscribing you. Please try again later.')

def showSubscribers(update, context):################################显示所有订阅者的chat_id和名字

    try:
        subscriber_ids = redis1.smembers('subscribers')
        if subscriber_ids:
            for chat_id in subscriber_ids:
                chat_id = chat_id.decode('utf-8')

                # Create a redis key for the user name
                redis_key = f"chat_id_{chat_id}_name"

                # Get the name from Redis
                name = redis1.get(redis_key)
                if name is not None:
                    name = name.decode('utf-8')

                update.message.reply_text(f"ID: {chat_id}.  {name if name else 'Not set'}")

    except Exception as e:
        update.message.reply_text(f"Error retrieving subscribers: {e}")


def showAllData(update, context):
    """显示Redis中的所有数据"""###################################################显示Redis中的所有数据
    try:
        # 获取所有的键
        all_keys = redis1.keys('*')
        if all_keys:
            print("All data in Redis:")
            for key in all_keys:
                key = key.decode('utf-8')
                # 获取键的类型
                key_type = redis1.type(key).decode('utf-8')
                # 根据类型获取值
                if key_type == 'string':
                    value = redis1.get(key)
                    if value:
                        value = value.decode('utf-8')
                elif key_type == 'set':
                    value = redis1.smembers(key)
                    if value:
                        value = ', '.join([v.decode('utf-8') for v in value])
                else:
                    value = 'Unsupported type: ' + key_type
                print(f"{key}: {value}")
                update.message.reply_text(f"{key}: {value}")
        else:
            print("No data found.")
    except Exception as e:
        print(f"Error retrieving data: {e}")

def get_transcript(update: Update, context: CallbackContext) -> None:###############################################显示字幕
    try:
        video_id = context.args[0]  # 从命令中获取YouTube视频ID
        transcript = get_youtube_transcript(video_id)
        if transcript:
            for item in transcript:
                update.message.reply_text(item['text'])
        else:
            update.message.reply_text('未能找到可用字幕。')
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /transcript <YouTube Video ID>')

# 定义get_youtube_transcript函数#####################帮助上一个功能。。
def get_youtube_transcript(video_id):
    # 获取视频的所有可用字幕语言
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

    # 创建一个语言列表
    languages = [transcript.language_code for transcript in transcript_list]

    # 尝试获取每种语言的字幕，直到找到一个可用的为止
    for lang in languages:
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
            return transcript
        except:
            continue


    return None

def contains_chinese(text: str) -> bool:
    """检查文本中是否包含中文字符"""
    return any('\u4e00' <= char <= '\u9fff' for char in text)

def get_transcript2(update: Update, context: CallbackContext) -> None: #########################################让gpt总结字幕
    try:
        video_id = context.args[0]  # 从命令中获取YouTube视频ID
        video_id = re.search(r'v=([^&]+)', video_id)
        video_id = video_id.group(1) if video_id else video_id  # 如果没有找到v=, 则URL本身被认为是视频ID
        transcript = get_youtube_transcript(video_id)
        if transcript:
            # 连接所有的字幕文本
            full_transcript = ' '.join([item['text'] for item in transcript])
            # 根据文本是否包含中文字符来设置字符限制
            char_limit = 500 if contains_chinese(full_transcript) else 2500
            full_transcript = full_transcript[:char_limit]
            # 通过HKBU_ChatGPT进行总结
            summary = chatgpt.submit( f"{full_transcript}这些为视频字幕,请用中、英两种语言说一遍本视频介绍,不要提到字幕，介绍视频内容:language=zh, en ,max_tokens=150,")



            # 返回总结
            update.message.reply_text(summary)
            save_message_to_redis(update.effective_chat.id, summary)
        else:
            update.message.reply_text('未能找到可用字幕。')
            
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /transcript <YouTube Video ID>')


def add_user_info_decorator(func):####################################用于在转发信息时添加用户名字
    def wrapper(update, context, *args, **kwargs):
        # 调用原始函数
        func(update, context, *args, **kwargs)

        # 获取执行命令的用户的 chat_id
        user_chat_id = update.effective_chat.id
        redis_key = f"chat_id_{user_chat_id}_name"

        # 尝试从 Redis 获取自定义名字
        user_name = redis1.get(redis_key)
        if user_name:
            user_name = user_name.decode('utf-8')  # Redis 保存的字符串是字节串，需要解码
            message = f"By {user_chat_id}. {user_name}"
        else:
            # 如果没有设置名字，只显示 chat_id
            message = f"By {user_chat_id}."

        # 从 Redis 获取所有订阅者
        subscribers = redis1.smembers('subscribers')
        if subscribers:
            for subscriber in subscribers:
                subscriber_chat_id = int(subscriber)  # Redis 保存的是字节串，需要转换为整数
                # 确保不把消息发送给使用功能的用户本人
                if subscriber_chat_id != user_chat_id:
                    context.bot.send_message(chat_id=subscriber_chat_id, text=message)

    return wrapper



@add_user_info_decorator
def broadcast_subscribers(update: Update, context: CallbackContext) -> None:###############################向所有用户发送一条自己的信息
    """Broadcast a message to all subscribers."""
    # 获取要广播的消息
    try:
        message = ' '.join(context.args)  # 修改此处以获取整个消息，而不仅是第一个词
        if not message:
            raise ValueError("Message is empty")
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /broadcast_subscribers <message>')
        return

    sender_id = str(update.effective_user.id)

    # 获取所有订阅者的 ID
    subscriber_ids = redis1.smembers('subscribers')

    # 向所有订阅者广播消息，除了消息的发送者
    for subscriber_id in subscriber_ids:
        subscriber_id = subscriber_id.decode('utf-8')
        if subscriber_id != sender_id:  # 检查以确保不向自己发送消息
            context.bot.send_message(chat_id=subscriber_id, text=message)


@add_user_info_decorator
def broadcast_last_reply_to_all_subscribers(update: Update, context: CallbackContext) -> None:#################向所有用户发送一条来自他的chatbot对话
    """Broadcast the last reply message of the command user to all subscribers."""
    try:
        # Check if the user is a subscriber
        is_subscriber(update.effective_user.id, update)
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /broadcast_last_reply_to_all_subscribers')
        return

    # Get the last reply message of the command user from Redis
    redis_key = f"chat_id_{update.effective_user.id}_last_reply"
    last_reply_message = redis1.get(redis_key)

    if last_reply_message is None:
        update.message.reply_text(f"No last reply message found for your chat_id.")
        return

    last_reply_message = last_reply_message.decode('utf-8')
    sender_id = str(update.effective_user.id)

    # Get all subscriber IDs
    subscriber_ids = redis1.smembers('subscribers')

    # Broadcast the last reply message to all subscribers
    for subscriber_id in subscriber_ids:
        subscriber_id = subscriber_id.decode('utf-8')
        if subscriber_id != sender_id:  # 检查以确保不向自己发送消息
                context.bot.send_message(chat_id=subscriber_id, text=last_reply_message)

def weather_command(update: Update, context: CallbackContext) -> None:##########################天气查询功能
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("香港", callback_data="810000"), InlineKeyboardButton("湾仔区", callback_data="810002")],
        [InlineKeyboardButton("东区", callback_data="810003"), InlineKeyboardButton("南区", callback_data="810004")],
        [InlineKeyboardButton("油尖旺区", callback_data="810005"), InlineKeyboardButton("深水埗区", callback_data="810006")],
        [InlineKeyboardButton("九龙城区", callback_data="810007"), InlineKeyboardButton("黄大仙区", callback_data="810008")],
        [InlineKeyboardButton("观塘区", callback_data="810009"), InlineKeyboardButton("荃湾区", callback_data="810010")],
        [InlineKeyboardButton("屯门区", callback_data="810011"), InlineKeyboardButton("元朗区", callback_data="810012")],
        [InlineKeyboardButton("大埔区", callback_data="810013"), InlineKeyboardButton("北区", callback_data="810014")],
        [InlineKeyboardButton("西贡区", callback_data="810015"), InlineKeyboardButton("沙田区", callback_data="810016")],
        [InlineKeyboardButton("葵青区", callback_data="810017"), InlineKeyboardButton("离岛区", callback_data="810018")],
    ])

    update.message.reply_text("Please select a district:", reply_markup=keyboard)

def button(update: Update, context: CallbackContext) -> None:############################用于响应上一个weather按选择区域按钮
    query = update.callback_query
    query.answer()

    city_code = query.data
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    api_key = config['weather_api']['api_key']


    weather_report = get_weather(api_key, city_code)
    weather_report_single_line = weather_report.replace("\n", " ")
    
    # 生成摘要
    summary = chatgpt.submit(f"{weather_report_single_line} 这些现在的天气，请给些建议，不要超过130字。")

    # Combine the weather report and the summary
    combined_report = weather_report + "\n\n" + "Summary: " + str(summary)

    # Send the combined report to the user
    query.edit_message_text(combined_report)
    save_message_to_redis(update.effective_chat.id, combined_report)

def convert(update: Update, context: CallbackContext) -> None:############################货币汇率转换
    try:
        amount = float(context.args[0])  # Amount to convert
        from_currency = context.args[1].upper()  # Source currency code
        to_currency = context.args[2].upper()  # Target currency code
        converted_amount = convert_currency(amount, from_currency, to_currency)
        if converted_amount:
            update.message.reply_text(f'{amount} {from_currency} equals {converted_amount} {to_currency}')
            response_message = f'{amount} {from_currency} equals {converted_amount} {to_currency}'
            save_message_to_redis(update.effective_chat.id, response_message)
        else:
            update.message.reply_text('Failed to convert currency. Please check your input.')
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /convert <amount> <from_currency> <to_currency>')
        


def convert_currency(amount, from_currency, to_currency):###################协助上一个功能
    config = configparser.ConfigParser()
    config.read('config.ini')
    api_key = config['currency_api']['api_key']
    url = f'http://api.tanshuapi.com/api/exchange/v1/index?key={api_key}&from={from_currency}&to={to_currency}&money={amount}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print(data)  # result data from API
        if 'code' in data and data['code'] == 1 and 'data' in data:
            exchange_data = data['data']
            converted_amount = float(exchange_data['exchange']) * amount
            return converted_amount
    return None




if __name__ == '__main__':
    main()
