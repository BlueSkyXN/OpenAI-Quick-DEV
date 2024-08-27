from flask import Flask, request, jsonify
import uuid
import requests
import random
import time

app = Flask(__name__)

def generate_user_agent():
    os_list = [
        'Windows NT 10.0; Win64; x64',
        'Macintosh; Intel Mac OS X 10_15_7',
        'X11; Linux x86_64'
    ]

    browser_list = [
        ('Chrome', 'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{}.{}.{}.{} Safari/537.36'),
        ('Firefox', 'Gecko/20100101 Firefox/{}.{}.{}'),
        ('Safari', 'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{}.{}.{} Safari/605.1.15'),
        ('Edge', 'Edge/{}.{}.{}.{}')
    ]

    os_choice = random.choice(os_list)
    browser_name, browser_format = random.choice(browser_list)

    major_version = random.randint(90, 122)
    minor_version = random.randint(0, 9)
    build_version = random.randint(0, 99)
    patch_version = random.randint(0, 99)

    if browser_name == 'Chrome':
        user_agent = f'Mozilla/5.0 ({os_choice}) {browser_format.format(major_version, minor_version, build_version, patch_version)}'
    elif browser_name == 'Firefox':
        user_agent = f'Mozilla/5.0 ({os_choice}; rv:{major_version}.0) {browser_format.format(major_version, minor_version, build_version)}'
    elif browser_name == 'Safari':
        user_agent = f'Mozilla/5.0 ({os_choice}) {browser_format.format(major_version, minor_version, build_version)}'
    else:
        user_agent = f'Mozilla/5.0 ({os_choice}) {browser_format.format(major_version, minor_version, build_version, patch_version)}'
    return user_agent

def get_header():
    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/json;charset=utf-8',
        'origin': 'https://web.talkx.cn',
        'referer': 'https://web.talkx.cn/',
        'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'talkx-token': '',  # 在这里填入有效的 token
        'Accept-Charset': 'utf-8',
        'user-agent': generate_user_agent(),
    }
    return headers

def forward_request_to_talkx(messages):
    json_data = {
        'roleType': '0',
        'productId': 0,
        'sessionId': str(uuid.uuid4()),
        'messages': messages,
    }

    response = requests.post('https://api.talkx.cn/gpt/chat', headers=get_header(), json=json_data)
    response.encoding = 'utf-8'

    content_type = response.headers.get('Content-Type', '')

    if response.status_code == 200:
        if 'application/json' in content_type:
            return response.json()
        else:
            return {"choices": [{"message": {"role": "assistant", "content": response.text}}]}
    else:
        return {"error": "Failed to fetch response from talkx API", "status_code": response.status_code, "content": response.text}

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    openai_request = request.json
    messages = [{"role": message["role"], "content": message["content"]} for message in openai_request.get("messages", [])]

    talkx_response = forward_request_to_talkx(messages)

    openai_response = {
        "id": str(uuid.uuid4()),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "gpt-3.5-turbo",
        "choices": talkx_response.get("choices", []),
        "usage": {
            "prompt_tokens": len(openai_request.get("messages", [])),
            "completion_tokens": len(talkx_response.get("choices", [])),
            "total_tokens": len(openai_request.get("messages", [])) + len(talkx_response.get("choices", []))
        }
    }

    return jsonify(openai_response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
