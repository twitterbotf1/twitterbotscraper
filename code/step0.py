import os

def clean_directory():
    directory = "/workspaces/twitterbotscraper/code"
    whitelist = {
        "key.txt", "sources.txt", "step0.py", "step1.py", 
        "step2.py", "step3.py", "step4.py", "step5.py"
    }

    for filename in os.listdir(directory):
        if filename not in whitelist:
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

if __name__ == "__main__":
    clean_directory()