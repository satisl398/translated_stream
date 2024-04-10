import random
from hashlib import md5, sha256
import os
import requests
import hmac
import json
import time
from datetime import datetime
from http.client import HTTPSConnection


def baidu_api(sentences, from_lang, to_lang):
    endpoint = 'http://api.fanyi.baidu.com'
    path = '/api/trans/vip/translate'
    url = endpoint + path
    appid = os.environ.get('baidu_appid')
    appkey = os.environ.get('baidu_appkey')
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    infos = []
    timestamps = []
    query = ''
    for sentence in sentences:
        query += f'{sentence["text"]}\n'
        timestamps.append((sentence['start'], sentence['end']))
        # 若字节过多，则提交
        if len(query.encode('utf-8')) > 6000 * 0.8:
            infos.append((query.strip('\n'), timestamps))
            query = ''
            timestamps = []
    if len(query) != 0:
        infos.append((query.strip('\n'), timestamps))

    results = []
    for query, timestamps in infos:
        salt = random.randint(32768, 65536)
        sign = md5((appid + query + str(salt) + appkey).encode('utf-8')).hexdigest()
        payload = {'appid': appid, 'q': query, 'from': from_lang, 'to': to_lang, 'salt': salt, 'sign': sign}
        with requests.post(url, params=payload, headers=headers) as r:
            for idx, i in enumerate(r.json()['trans_result']):
                results.append(
                    {'text': '%s\n%s' % (i['src'], i['dst']), 'start': timestamps[idx][0], 'end': timestamps[idx][1]}
                )
        time.sleep(0.2)
    return results


def tencent_api(sentences, from_lang, to_lang, projectid=0):
    def sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), sha256).digest()

    def request(query):
        secret_id = os.environ.get('tencent_appid')
        secret_key = os.environ.get('tencent_appkey')

        service = "tmt"
        host = "tmt.tencentcloudapi.com"
        region = "ap-guangzhou"
        version = "2018-03-21"
        action = "TextTranslate"

        payload = json.dumps(
            {'SourceText': query, 'Source': from_lang, 'Target': to_lang, 'ProjectId': projectid})
        algorithm = "TC3-HMAC-SHA256"
        timestamp = int(time.time())
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

        # ************* 步骤 1：拼接规范请求串 *************
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        ct = "application/json; charset=utf-8"
        canonical_headers = "content-type:%s\nhost:%s\nx-tc-action:%s\n" % (ct, host, action.lower())
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (http_request_method + "\n" +
                             canonical_uri + "\n" +
                             canonical_querystring + "\n" +
                             canonical_headers + "\n" +
                             signed_headers + "\n" +
                             hashed_request_payload)

        # ************* 步骤 2：拼接待签名字符串 *************
        credential_scope = date + "/" + service + "/" + "tc3_request"
        hashed_canonical_request = sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = (algorithm + "\n" +
                          str(timestamp) + "\n" +
                          credential_scope + "\n" +
                          hashed_canonical_request)

        # ************* 步骤 3：计算签名 *************
        secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = sign(secret_date, service)
        secret_signing = sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), sha256).hexdigest()

        # ************* 步骤 4：拼接 Authorization *************
        authorization = (algorithm + " " +
                         "Credential=" + secret_id + "/" + credential_scope + ", " +
                         "SignedHeaders=" + signed_headers + ", " +
                         "Signature=" + signature)

        # ************* 步骤 5：构造并发起请求 *************
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Timestamp": timestamp,
            "X-TC-Version": version,
            "X-TC-Region": region
        }

        req = HTTPSConnection(host)
        req.request("POST", "/", headers=headers, body=payload.encode("utf-8"))
        resp = req.getresponse()
        target_text = json.loads(resp.read().decode('utf-8'))
        return target_text['Response']['TargetText']

    infos = []
    timestamps = []
    query = ''
    for sentence in sentences:
        query += f'{sentence["text"]}\n'
        timestamps.append((sentence['start'], sentence['end']))
        # 若字节过多，则提交
        if len(query.encode('utf-8')) > 6000 * 0.8:
            infos.append((query.strip('\n'), timestamps))
            query = ''
            timestamps = []
    if len(query) != 0:
        infos.append((query.strip('\n'), timestamps))
    results = []
    for query, timestamps in infos:
        for src_text, dst_text, (start, end) in zip(query.split('\n'), request(query).split('\n'), timestamps):
            results.append(
                {'text': '%s\n%s' % (src_text, dst_text), 'start': start, 'end': end}
            )
            time.sleep(0.2)
    return results


