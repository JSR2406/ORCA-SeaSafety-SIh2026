import urllib.request

html = urllib.request.urlopen("http://localhost:3000/ai-copilot").read().decode("utf-8")
idx = html.find("terminal-bulletin-entry")
if idx != -1:
    print(html[idx:idx+2500])
else:
    print("Not found")
