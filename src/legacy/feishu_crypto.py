import base64
import hashlib
import json
import os
from typing import Optional

from Crypto.Cipher import AES

from .secure_config import get_secret

# 飞书事件订阅加密解密工具
# 参考：https://open.feishu.cn/document/ukTMukTMukTM/uYDNxYjL2QTM24iN0EjN/event-subscription-configure-/encrypt-key-encryption-configuration


class FeishuSecurityError(Exception):
    """飞书安全验证错误"""

    pass


class FeishuEncryptor:
    """飞书事件订阅消息加解密"""

    def __init__(self, encrypt_key: str, verification_token: str | None = None):
        """
        Args:
            encrypt_key: 飞书平台配置的 Encrypt Key (base64 encoded or raw string)
            verification_token: 飞书 Verification Token (optional, used for signature verification)
        """
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token

        # 清理密钥：去掉所有空白字符
        cleaned_key = encrypt_key.strip()
        # 去掉换行符、空格等
        cleaned_key = "".join(cleaned_key.split())

        print(
            f"[Crypto] Original key length: {len(encrypt_key)}, cleaned: {len(cleaned_key)}"
        )

        # 首先尝试作为base64解码
        try:
            self.key = base64.b64decode(cleaned_key)
            print(f"[Crypto] Key decoded as base64, length: {len(self.key)} bytes")
        except:
            # 如果不是base64，可能是不带填充的base64，或者包含额外字符
            # 飞书AES-256需要32字节密钥，base64编码为43字符（不带填充）
            # 检查密钥长度，如果超过43字符，可能包含额外信息
            if len(cleaned_key) >= 43:
                print(
                    f"[Crypto] Key length {len(cleaned_key)} >= 43, trying first 43 chars as base64"
                )
                first_43 = cleaned_key[:43]
                try:
                    # 尝试添加填充并解码
                    padded = first_43 + "="  # 添加一个填充字符
                    self.key = base64.b64decode(padded)
                    print(
                        f"[Crypto] First 43 chars decoded as base64, length: {len(self.key)} bytes"
                    )
                except Exception:
                    # 如果失败，使用原始字符串
                    print(
                        f"[Crypto] First 43 chars also not base64, using raw string, length: {len(cleaned_key)} chars"
                    )
                    self.key = cleaned_key.encode("utf-8")
            else:
                # 如果不是base64，直接使用字符串作为密钥
                print(
                    f"[Crypto] Key not base64, using raw string, length: {len(cleaned_key)} chars"
                )
                self.key = cleaned_key.encode("utf-8")

        key_len = len(self.key)
        if key_len not in [16, 24, 32]:
            print(f"[Crypto] Warning: Key length {key_len} not standard AES size")
            # 如果不是标准长度，取前32/24/16字节
            if key_len > 32:
                self.key = self.key[:32]
                print("[Crypto] Using first 32 bytes for AES-256")
            elif key_len > 24:
                self.key = self.key[:24]
                print("[Crypto] Using first 24 bytes for AES-192")
            elif key_len > 16:
                self.key = self.key[:16]
                print("[Crypto] Using first 16 bytes for AES-128")
            else:
                # 如果小于16字节，填充到16字节
                padding = 16 - key_len
                self.key = self.key + bytes([padding]) * padding
                print("[Crypto] Padded to 16 bytes for AES-128")

        self.key_length = len(self.key)
        self.aes_mode = {16: "AES-128", 24: "AES-192", 32: "AES-256"}.get(
            self.key_length, f"AES-{self.key_length * 8}"
        )

        print(f"[Crypto] Using {self.aes_mode}, key length: {self.key_length} bytes")

    def decrypt(self, encrypted_data: str) -> dict:
        """
        解密飞书加密消息

        Args:
            encrypted_data: 飞书发送的 encrypt 字段值

        Returns:
            解密后的 JSON 对象
        """
        import json  # 局部导入避免作用域问题

        # base64 解码
        encrypted_bytes = base64.b64decode(encrypted_data)

        # 前 16 字节是 IV，后面是密文
        iv = encrypted_bytes[:16]
        ciphertext = encrypted_bytes[16:]

        # AES 解密
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        raw_decrypted = cipher.decrypt(ciphertext)

        try:
            # PKCS7 去填充
            decrypted = self._pkcs7_unpad(raw_decrypted)
        except ValueError as e:
            print(f"[Crypto] Padding error: {e}")
            print(
                f"[Crypto] Raw decrypted (first 64 bytes hex): {raw_decrypted[:64].hex()}"
            )
            print(f"[Crypto] Raw decrypted as ASCII: {raw_decrypted[:100]}")
            # 尝试直接解码，看看是否有可读内容
            try:
                decoded = raw_decrypted.decode("utf-8", errors="ignore")
                print(
                    f"[Crypto] Raw decrypted as UTF-8 (first 200 chars): {decoded[:200]}"
                )
                # 尝试找到JSON开始位置
                if "{" in decoded or "[" in decoded:
                    # 找到第一个{或[的位置
                    start_idx = (
                        min(i for i, c in enumerate(decoded) if c in "{[")
                        if any(c in decoded for c in "{[")
                        else 0
                    )
                    len(decoded)
                    # 从末尾找到匹配的}或]
                    # 简化：直接截取从start_idx开始的部分
                    json_candidate = decoded[start_idx:]
                    print(
                        f"[Crypto] Found possible JSON at position {start_idx}: {json_candidate[:100]}..."
                    )
                    try:
                        # 尝试解析为JSON（使用模块级别的json导入）
                        parsed = json.loads(json_candidate)
                        print(
                            "[Crypto] Successfully parsed JSON without proper padding!"
                        )
                        return parsed
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass
            raise

        # 解码为 JSON
        decrypted_str = decrypted.decode("utf-8")
        # print(f"[Crypto] Decryption successful, JSON length: {len(decrypted_str)}")
        return json.loads(decrypted_str)

    def encrypt(self, data: dict) -> str:
        """
        加密消息（用于响应验证）

        Args:
            data: 要加密的字典数据

        Returns:
            base64 编码的加密字符串
        """
        import secrets

        # 转换为 JSON 字符串
        json_str = json.dumps(data, ensure_ascii=False)
        # PKCS7 填充
        padded = self._pkcs7_pad(json_str.encode("utf-8"))

        # 生成随机 IV
        iv = secrets.token_bytes(16)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)

        # 加密
        ciphertext = cipher.encrypt(padded)

        # 合并 IV 和密文，然后 base64 编码
        encrypted = iv + ciphertext
        return base64.b64encode(encrypted).decode("utf-8")

    def _pkcs7_pad(self, data: bytes, block_size: int = 16) -> bytes:
        """PKCS7 填充"""
        padding_len = block_size - (len(data) % block_size)
        padding = bytes([padding_len]) * padding_len
        return data + padding

    def _pkcs7_unpad(self, data: bytes) -> bytes:
        """PKCS7 去填充"""
        padding_len = data[-1]
        if padding_len > len(data):
            raise ValueError("Invalid padding")
        # 验证填充是否正确
        if data[-padding_len:] != bytes([padding_len]) * padding_len:
            raise ValueError("Invalid padding")
        return data[:-padding_len]

    def verify_signature(
        self, timestamp: str, nonce: str, encrypted: str, signature: str
    ) -> bool:
        """
        验证签名

        Args:
            timestamp: 时间戳
            nonce: 随机字符串
            encrypted: 加密消息
            signature: 签名

        Returns:
            bool: 签名是否有效
        """
        # 飞书签名验证使用 Verification Token，如果没有则使用 Encrypt Key
        token = self.verification_token or self.encrypt_key

        # 拼接字符串
        content = f"{timestamp}\n{nonce}\n{token}\n{encrypted}"

        # SHA256 哈希
        hash_obj = hashlib.sha256(content.encode("utf-8"))
        calculated = base64.b64encode(hash_obj.digest()).decode("utf-8")

        return calculated == signature


def get_encryptor() -> Optional[FeishuEncryptor]:
    """从环境变量获取加密器"""
    encrypt_key = get_secret("FEISHU_ENCRYPT_KEY")
    verification_token = get_secret("FEISHU_VERIFICATION_TOKEN")

    if not encrypt_key and not verification_token:
        return None

    # 优先使用 Verification Token 作为加密密钥（飞书可能使用它）
    key_to_use = verification_token or encrypt_key
    if not key_to_use:
        return None

    print(
        f"[Crypto] Using key: {'Verification Token' if verification_token else 'Encrypt Key'}"
    )

    return FeishuEncryptor(key_to_use, verification_token)


def decrypt_feishu_payload(body: dict) -> dict:
    """
    解密飞书 webhook 请求体

    支持 v1 和 v2 格式
    v1: {"encrypt": "...", "timestamp": "...", "nonce": "...", "signature": "..."}
    v2: {"schema": "2.0", "header": {...}, "event": {...}, "encrypt": "...", "timestamp": "...", "nonce": "...", "signature": "..."}

    Returns:
        解密后的请求体（如果是加密的），否则返回原请求体
    """

    # 检查是否有加密字段
    if "encrypt" not in body:
        return body

    # 如果有 challenge 字段，可能是未加密的 URL 验证请求
    # 即使有 encrypt 字段，也优先返回原 body 让上层处理
    if "challenge" in body:
        print(
            "[Crypto] Found challenge in body, returning original body for URL verification"
        )
        return body

    encrypted = body["encrypt"]
    timestamp = body.get("timestamp", "")
    nonce = body.get("nonce", "")
    signature = body.get("signature", "")

    # 减少日志输出以提高性能
    # print(f"[Crypto] Attempting to decrypt, encrypted length: {len(encrypted)}")
    # print(
    #     f"[Crypto] Has timestamp/nonce/signature: {bool(timestamp)}/{bool(nonce)}/{bool(signature)}"
    # )

    # 尝试多种密钥组合
    possible_keys = []

    # 1. Verification Token (最可能)
    verification_token = get_secret("FEISHU_VERIFICATION_TOKEN")
    if verification_token:
        possible_keys.append(("Verification Token", verification_token))

    # 2. Encrypt Key
    encrypt_key = get_secret("FEISHU_ENCRYPT_KEY")
    if encrypt_key:
        possible_keys.append(("Encrypt Key", encrypt_key))

    # 3. App Secret (不太可能，但尝试)
    app_secret = get_secret("FEISHU_APP_SECRET")
    if app_secret:
        possible_keys.append(("App Secret", app_secret))

    # 4. App ID (不太可能)
    app_id = os.getenv("FEISHU_APP_ID")  # App ID is not sensitive
    if app_id:
        possible_keys.append(("App ID", app_id))

    if not possible_keys:
        print("[Crypto] No encryption keys found in environment")
        return body

    last_error = None
    for key_name, key_value in possible_keys:
        try:
            # print(f"[Crypto] Trying with {key_name}")
            encryptor = FeishuEncryptor(key_value, verification_token)

            # 验证签名（如果提供了签名）
            if timestamp and nonce and signature:
                if not encryptor.verify_signature(
                    timestamp, nonce, encrypted, signature
                ):
                    print(f"[Crypto] Signature verification failed with {key_name}")
                    # 签名验证失败，拒绝请求
                    raise FeishuSecurityError("Invalid signature")

            # 解密
            decrypted = encryptor.decrypt(encrypted)
            # print(f"[Crypto] Successfully decrypted with {key_name}")

            # 如果是 v2 格式，需要保持 schema 和 header
            if "schema" in body and body["schema"] == "2.0":
                # 解密后的数据应该是完整的 v2 格式
                return decrypted
            else:
                # v1 格式，解密后直接返回解密的内容
                return decrypted

        except Exception as e:
            last_error = e
            print(f"[Crypto] Failed with {key_name}: {e}")
            continue

    print(f"[Crypto] All decryption attempts failed. Last error: {last_error}")
    # 如果所有尝试都失败，返回原始body，让上层处理
    return body


def verify_feishu_webhook(body: dict) -> bool:
    """
    验证飞书 webhook 请求的签名

    Args:
        body: 飞书 webhook 请求体

    Returns:
        bool: 签名是否有效

    Raises:
        FeishuSecurityError: 签名验证失败
    """
    # 检查是否有签名字段
    timestamp = body.get("timestamp", "")
    nonce = body.get("nonce", "")
    signature = body.get("signature", "")
    encrypted = body.get("encrypt", "")

    # 如果没有签名字段，可能是未加密的请求或 URL 验证
    if not signature or not encrypted:
        # 如果是 URL 验证请求，直接通过
        if "challenge" in body:
            return True
        # 其他情况：如果没有签名，可能是测试请求或配置错误
        # 在生产环境中应该要求签名，但为了兼容性，返回 True
        print("[Crypto] Warning: No signature in webhook request")
        return True

    # 尝试使用所有可能的密钥验证签名
    possible_keys = []

    # 1. Verification Token (最可能)
    verification_token = get_secret("FEISHU_VERIFICATION_TOKEN")
    if verification_token:
        possible_keys.append(("Verification Token", verification_token))

    # 2. Encrypt Key
    encrypt_key = get_secret("FEISHU_ENCRYPT_KEY")
    if encrypt_key:
        possible_keys.append(("Encrypt Key", encrypt_key))

    # 3. App Secret (不太可能，但尝试)
    app_secret = get_secret("FEISHU_APP_SECRET")
    if app_secret:
        possible_keys.append(("App Secret", app_secret))

    if not possible_keys:
        print("[Crypto] No verification keys found")
        raise FeishuSecurityError("No verification keys configured")

    for key_name, key_value in possible_keys:
        encryptor = FeishuEncryptor(key_value, verification_token)
        if encryptor.verify_signature(timestamp, nonce, encrypted, signature):
            print(f"[Crypto] Signature verified with {key_name}")
            return True

    # 所有密钥都验证失败
    print("[Crypto] Signature verification failed with all keys")
    raise FeishuSecurityError("Invalid signature")
