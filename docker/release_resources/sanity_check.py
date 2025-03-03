"""Sanity checks, to be sure that our package is usable"""
import argparse
import random
import shutil
from pathlib import Path

import numpy
from concrete.numpy.compilation import configuration
from concrete.numpy.compilation.compiler import Compiler
from concrete.numpy.compilation.configuration import Configuration
from sklearn.datasets import make_classification
from sklearn.metrics import average_precision_score, confusion_matrix
from sklearn.model_selection import train_test_split

# pylint: disable=ungrouped-imports
from concrete import ml
from concrete.ml.sklearn import DecisionTreeClassifier as ConcreteDecisionTreeClassifier

# pylint: enable=ungrouped-imports


def ml_check(args, keyring_dir_as_str):
    """Test about Concrete ML functions"""

    is_fast = args.fast

    print(ml.__version__)

    features, classes = make_classification(
        n_samples=1000,
        n_features=10,
        n_classes=2,
        n_informative=5,
        n_redundant=0,
        n_clusters_per_class=1,
        weights=(0.2, 0.8),
    )
    classes = classes.astype(numpy.int64)

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        classes,
        test_size=0.15,
        random_state=42,
    )

    model = ConcreteDecisionTreeClassifier(n_bits=3, max_depth=6)
    model.fit(x_train, y_train)

    # Compute average precision on test

    y_pred = model.predict(x_test)
    average_precision = average_precision_score(y_test, y_pred)
    print(f"Average precision-recall score: {average_precision:0.2f}")

    y_pred = model.predict(x_test)
    true_negative, false_positive, false_negative, true_positive = confusion_matrix(
        y_test, y_pred, normalize="true"
    ).ravel()

    num_samples = len(y_test)
    num_spam = sum(y_test)

    print(f"Number of test samples: {num_samples}")
    print(f"Number of negatives in test samples: {num_spam}")

    print(f"True Negative rate: {true_negative}")
    print(f"False Positive rate: {false_positive}")
    print(f"False Negative rate: {false_negative}")
    print(f"True Positive rate: {true_positive}")

    # We first compile the model with some data, here the training set
    model.compile(
        x_train,
        configuration=Configuration(
            enable_unsafe_features=True,  # This is for our tests only, never use that in prod
            use_insecure_key_cache=is_fast,  # This is for our tests only, never use that in prod
            insecure_key_cache_location=keyring_dir_as_str,
            p_error=None,
            global_p_error=None,
        ),
        use_virtual_lib=True,
    )

    nb_samples = 1 if is_fast else 10

    # Predict in VL for a few examples
    y_pred_vl = model.predict(x_test[:nb_samples], execute_in_fhe=True)

    # Check prediction VL vs sklearn
    print(f"Prediction VL:      {y_pred_vl}")
    print(f"Prediction sklearn: {y_pred[:nb_samples]}")

    print(
        f"{numpy.sum(y_pred_vl==y_pred[:nb_samples])}/{nb_samples} "
        "predictions are similar between the VL model and the clear sklearn model."
    )


def cn_check(args, keyring_dir_as_str):
    """Test about Concrete Numpy functions"""

    is_fast = args.fast

    def function_to_compile(x):
        return x + 42

    n_bits = 3

    compiler = Compiler(
        function_to_compile,
        {"x": "encrypted"},
    )
    config = Configuration(
        enable_unsafe_features=is_fast,  # This is for our tests only, never use that in prod
        use_insecure_key_cache=is_fast,  # This is for our tests only, never use that in prod
        insecure_key_cache_location=keyring_dir_as_str,
    )

    print("Compiling...")

    engine = compiler.compile(range(2**n_bits), config)

    inputs = []
    labels = []
    nb_samples = 1 if is_fast else 4

    for _ in range(nb_samples):
        sample_x = random.randint(0, 2**n_bits - 1)

        inputs.append([sample_x])
        labels.append(function_to_compile(*inputs[-1]))

    correct = 0
    for idx, (input_i, label_i) in enumerate(zip(inputs, labels), 1):
        print(f"Inference #{idx}")
        result_i = engine.encrypt_run_decrypt(*input_i)

        if result_i == label_i:
            correct += 1

    print(f"{correct}/{len(inputs)}")


def main(args):
    """Entry point"""

    is_fast = args.fast

    keyring_dir_as_str = None
    if is_fast:
        keyring_dir = Path.home().resolve() / "ConcreteNumpyKeyCache"
        keyring_dir.mkdir(parents=True, exist_ok=True)
        keyring_dir_as_str = str(keyring_dir)
        print(f"Using {keyring_dir_as_str} as key cache dir")
        configuration._INSECURE_KEY_CACHE_LOCATION = (  # pylint: disable=protected-access
            keyring_dir_as_str
        )

    ml_check(args, keyring_dir_as_str)
    cn_check(args, keyring_dir_as_str)

    if is_fast:
        keyring_dir = Path.home().resolve() / "ConcreteNumpyKeyCache"
        if keyring_dir is not None:
            # Remove incomplete keys
            for incomplete_keys in keyring_dir.glob("**/*incomplete*"):
                shutil.rmtree(incomplete_keys, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(allow_abbrev=False)

    parser.add_argument(
        "--fast",
        action="store_true",
        help="do a single test, just to check that the code is correct.",
    )

    cli_args = parser.parse_args()

    main(cli_args)
