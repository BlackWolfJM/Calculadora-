import os
import urllib.request
import zipfile

url = "https://github.com/KaTeX/KaTeX/releases/download/v0.16.9/katex.zip"
zip_path = "katex.zip"
extract_path = "src/presentation/assets" # Extraerá una carpeta llamada "katex"

print("Downloading KaTeX...")
urllib.request.urlretrieve(url, zip_path)

print("Extracting...")
os.makedirs(extract_path, exist_ok=True)
with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_path)

os.remove(zip_path)
print("KaTeX offline assets downloaded successfully!")
