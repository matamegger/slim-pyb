import os.path
import sys
from pathlib import Path


if __name__ == '__main__':
    main_file_path = os.path.expanduser(sys.argv[1])
    main_file = open(main_file_path, "r")
    parent_dir = Path(main_file_path).parent.absolute()

