import hashlib

import aiofiles


async def write_content(file_path: str, content: bytes) -> None:
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)


async def read_content(file_path: str) -> bytes:
    async with aiofiles.open(file_path, "rb") as f:
        return await f.read()


def hash_content(content: str) -> str:
    """Generate a hash for the content.
    :param content: Content to hash
    :return: SHA1 hash of the content
    """
    return hashlib.sha1(content).hexdigest()
