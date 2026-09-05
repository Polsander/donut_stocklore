"""Random helper functions to use in local development"""

from pathlib import Path
import shutil


def rename_files_in_dir():
    # Define the directory path
    dir_path = Path("./data/test/images")

    # Loop through all files in the directory
    i = 0
    for file_path in dir_path.iterdir():
        # Make sure we are only renaming files (skipping subfolders)
        if file_path.is_file():
            # Example: Add a prefix to each filename
            new_name = f"test_receipt{i}.jpg"
            # Rename the file by combining the original directory path with the new name
            file_path.rename(dir_path / new_name)
            
            i += 1

def move_files_from_dir():
    dir_path = Path("./data/train/images")
    dst_path = Path("./data/validate/images")

    for i in range(501,626):
        src_file = dir_path / f"train_receipt{i}.jpg"

        if src_file.exists():
            shutil.move(str(src_file), str(dst_path))

if __name__ == "__main__":
    rename_files_in_dir()
