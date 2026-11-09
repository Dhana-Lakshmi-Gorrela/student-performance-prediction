"""Train the model:  python -m ml.train [path/to/students.csv]"""
import sys
from ml.model import train

if __name__ == "__main__":
    print(train(sys.argv[1] if len(sys.argv) > 1 else None))
