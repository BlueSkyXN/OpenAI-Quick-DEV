import random
import json
import aiohttp
import asyncio
from aiohttp import web
from datetime import datetime

# More： https://www.blueskyxn.com/202408/7089.html
# llama3.1-8b、llama3.1-70b
# 调试信息开关
DEBUG_MODE = False  # 设置为 True 可以打印详细的调试信息

# 定义固定的模型信息
DEFAULT_MODEL = "llama3.1-8b"
ALTERNATE_MODEL = "llama3.1-70b"
FIXED_URL = "https://api.cerebras.ai/v1/chat/completions"
FIXED_TEMPERATURE = 0.2
FIXED_TOP_P = 1
FIXED_MAX_TOKENS = 4096

# 记录基本信息的日志函数
def log_basic_info(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

# 异步发送请求并打印调试信息
async def send_request(auth_tokens, data):
    try:
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {auth_tokens[0]}",
            "content-type": "application/json"
        }

        # 检查传入的数据是否指定了 llama3.1-70b 模型
        requested_model = data.get("model", DEFAULT_MODEL)
        model_to_use = DEFAULT_MODEL
        if requested_model == ALTERNATE_MODEL:
            model_to_use = ALTERNATE_MODEL
        
        # 记录收到的模型请求以及实际使用的模型
        log_basic_info(f"Requested model: {requested_model}, Using model: {model_to_use}")
        
        # 构造请求体
        payload = {
            "messages": data.get("messages", []),
            "model": model_to_use,
            "temperature": FIXED_TEMPERATURE,
            "top_p": FIXED_TOP_P,
            "max_tokens": FIXED_MAX_TOKENS
        }

        if DEBUG_MODE:
            print("Request Payload:", json.dumps(payload, indent=4))
            print("Request Headers:", headers)

        async with aiohttp.ClientSession() as session:
            async with session.post(FIXED_URL, headers=headers, json=payload) as resp:
                response_text = await resp.text()

                # 尝试解析响应体
                response_json = json.loads(response_text)

                # 提取total_time和total_tokens信息
                total_tokens = response_json.get('usage', {}).get('total_tokens', 'N/A')
                total_time = response_json.get('time_info', {}).get('total_time', 'N/A')

                # 打印所有关键信息到同一行
                log_basic_info(f"Path: {FIXED_URL}, Status Code: {resp.status}, Total Tokens Used: {total_tokens}, Total Time: {total_time:.3f} seconds")

                return response_text

    except Exception as e:
        log_basic_info(f"Exception occurred: {str(e)}")

# 主函数
async def handle_request(request):
    try:
        # 获取请求数据
        request_data = await request.json()
        headers = dict(request.headers)

        # 检查并处理 Authorization 头
        authorization_header = headers.get('Authorization', '')
        auth_tokens = [auth.strip() for auth in authorization_header.replace('Bearer ', '').split(',')]
        
        if not auth_tokens:
            return web.json_response({"error": "Missing Authorization token"}, status=400)
        
        # 如果有多个 auth token，随机选择一个
        auth_token = random.choice(auth_tokens)
        headers['Authorization'] = f"Bearer {auth_token}"

        # 打印传入请求的基本信息
        log_basic_info(f"Received request for path: {request.path}")

        if DEBUG_MODE:
            print("Received Request Data:", json.dumps(request_data, indent=4))
            print("Received Headers:", headers)

        # 发送请求并获取响应
        response_text = await send_request(auth_tokens, request_data)

        # 返回最终的响应
        return web.json_response(json.loads(response_text))

    except Exception as e:
        log_basic_info(f"Exception occurred in handling request: {str(e)}")
        return web.json_response({"error": str(e)}, status=500)

# 设置路由
app = web.Application()
app.router.add_post('/v1/chat/completions', handle_request)

# 运行服务器，监听5804端口
if __name__ == '__main__':
    web.run_app(app, port=5804)
