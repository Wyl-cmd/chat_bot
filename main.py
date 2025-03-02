import atexit
import os
import uuid
import pygame
import edge_tts
import ollama
import asyncio
import configparser
import random
from datetime import datetime

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

# 注册退出处理函数
@atexit.register
def cleanup_mv_folder():
    if os.path.exists('mv'):
        for file_name in os.listdir('mv'):
            if file_name.endswith('.mp3'):
                os.remove(os.path.join('mv', file_name))
        print("Cleaned up 'mv' folder.")

# 存储对话历史，这里使用一个列表来存储每轮对话的prompt
conversation_history = []

# 全局变量，用于跟踪当前播放的音频文件
current_audio_file = None

async def generate_and_play_audio(text, rate="+75%"):
    global current_audio_file

    if not os.path.exists('mv'):
        os.makedirs('mv')

    file_name = f"mv/{uuid.uuid4()}.mp3"
    communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural", rate=rate)
    await communicate.save(file_name)

    pygame.init()
    pygame.mixer.init()  # 使用系统默认音频输出设备

    if current_audio_file and os.path.exists(current_audio_file):
        os.remove(current_audio_file)

    pygame.mixer.music.load(file_name)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    pygame.quit()

    current_audio_file = file_name

    return file_name

def get_ollama_response(prompt):
    try:
        # 假设 ollama 服务的地址和端口已经在 config.ini 中
        ollama_host = config['OLLAMA'].get('host', raw=True)
        ollama_port = config['OLLAMA'].get('port', raw=True)
        ollama_model = config['OLLAMA'].get('model', raw=True)

        # 创建 ollama 客户端
        client = ollama.Client(host=f"http://{ollama_host}:{ollama_port}")
        # 发起聊天请求
        response = client.chat(
            model=ollama_model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7, "max_tokens": 200}  # 根据需要调整参数
        )
        # 提取 ollama 的回复内容
        if response and "message" in response:
            return response["message"]["content"]
        else:
            return "抱歉，我无法获取回复。"
    except Exception as e:
        print(f"请求 ollama 服务时出错：{e}")
        return "抱歉，我无法获取回复。"

async def handle_user_input():
    last_input_time = datetime.now()
    max_idle_time = int(config['SETTINGS'].get('max_idle_time', 300))  # 从配置文件中读取最大空闲时间

    while True:
        try:
            # 等待用户输入，超时时间为10秒
            user_input = await asyncio.wait_for(asyncio.to_thread(input, "请输入你的消息: "), timeout=10)
            last_input_time = datetime.now()
            if user_input.lower() == "exit":
                break

            response = get_ollama_response(user_input)
            if response is not None:
                conversation_history.append(f"用户: {user_input}")
                conversation_history.append(f"AI: {response}")
                print(f"\033[32m{response}\033[0m")
                await generate_and_play_audio(response, rate="+10%")
        except asyncio.TimeoutError:
            # 如果10秒内没有输入，计算距离上次输入的时间
            time_since_last_input = (datetime.now() - last_input_time).total_seconds()
            if time_since_last_input >= 10:
                # 随机生成一个提示消息
                prompt = f"用户已经{int(time_since_last_input)}秒没有和你对话了，这条消息为系统发送，请不要告诉用户你收到了这条消息或和这条消息有关的任何内容，请说些简短的内容引起用户注意，当前时间为{datetime.now().strftime('%H:%M:%S')}"
                response = get_ollama_response(prompt)
                if response is not None:
                    conversation_history.append(f"AI: {response}")
                    print(f"\033[32m{response}\033[0m")
                    await generate_and_play_audio(response, rate="+10%")

# 创建事件循环并运行用户输入处理任务
loop = asyncio.get_event_loop()
loop.run_until_complete(handle_user_input())
