from urllib.parse import urlparse

parsed = urlparse('http://www.pearvideo.com/video_1446576')
print('netloc'+parsed.netloc)
print('path'+parsed.path)
print('params'+parsed.params)
print('query'+parsed.query)
print('hostname'+parsed.hostname)

print(type(parsed.hostname))

