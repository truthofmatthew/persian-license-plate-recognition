import splitfolders

def split_dataset(input_folder, output_folder, train_size=0.8, val_size=0.1, test_size=0.1):
    """
    Split the dataset into training, validation, and test sets.

    :param input_folder: Path to the folder containing the dataset to be split.
    :param output_folder: Path to the folder where the split dataset will be saved.
    :param train_size: Proportion of the dataset to include in the train split (default: 0.8).
    :param val_size: Proportion of the dataset to include in the validation split (default: 0.1).
    :param test_size: Proportion of the dataset to include in the test split (default: 0.1).
    """
    # Ensure that the ratios sum to 1
    if train_size + val_size + test_size != 1:
        raise ValueError("Train, validation, and test sizes must sum to 1.")

    splitfolders.ratio(input_folder, output=output_folder, seed=1337, ratio=(train_size, val_size, test_size))


input_folder = 'datasets/iranis'
output_folder = 'datasets/split'
split_dataset(input_folder, output_folder)
