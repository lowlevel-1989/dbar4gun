import os

def list_mice():
    mice = []
    input_dir = '/dev/input/'
    for entry in os.listdir(input_dir):
        if 'mouse' in entry:
            mice.append(os.path.join(input_dir, entry))
    return mice

mice = list_mice()
print(len(mice), mice)
