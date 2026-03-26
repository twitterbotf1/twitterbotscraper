import os

def clean_json():
    directory = "code"
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            os.remove(os.path.join(directory, filename))

if __name__ == "__main__":
    clean_json()
