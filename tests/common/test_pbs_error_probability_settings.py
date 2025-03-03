"""Tests for the sklearn linear models."""
import warnings
from inspect import signature

import numpy
import pytest
from sklearn.exceptions import ConvergenceWarning
from torch import nn

from concrete.ml.pytest.torch_models import FCSmall
from concrete.ml.pytest.utils import classifiers, regressors, sanitize_test_and_train_datasets
from concrete.ml.torch.compile import compile_torch_model

INPUT_OUTPUT_FEATURE = [5, 10]


@pytest.mark.parametrize("model, parameters", classifiers + regressors)
@pytest.mark.parametrize(
    "kwargs",
    [
        {"p_error": 0.03},
        {"p_error": 0.04, "global_p_error": None},
        {"global_p_error": 0.025},
        {"global_p_error": 0.036, "p_error": None},
        {},
        {"global_p_error": 0.038, "p_error": 0.39},
    ],
)
def test_config_sklearn(model, parameters, kwargs, load_data):
    """Testing with p_error and global_p_error configs with sklearn models."""

    x, y = load_data(**parameters)
    x_train = x[:-1]
    y_train = y[:-1]

    model_params, x, _, x_train, y_train, _ = sanitize_test_and_train_datasets(model, x, y)

    clf = model(**model_params)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        # Fit the model
        clf.fit(x_train, y_train)

    if kwargs.get("p_error", None) is not None and kwargs.get("global_p_error", None) is not None:
        with pytest.raises(ValueError) as excinfo:
            clf.compile(x_train, verbose_compilation=True, **kwargs)
        assert "Please only set one of (p_error, global_p_error) values" in str(excinfo.value)
    else:
        clf.compile(x_train, verbose_compilation=True, **kwargs)

    # FIXME: https://github.com/zama-ai/concrete-ml-internal/issues/2206
    #
    # Will check that we have expected probabilities


@pytest.mark.parametrize(
    "model",
    [pytest.param(FCSmall)],
)
@pytest.mark.parametrize(
    "kwargs",
    [
        {"p_error": 0.03},
        {"p_error": 0.04, "global_p_error": None},
        {"global_p_error": 0.025},
        {"global_p_error": 0.036, "p_error": None},
        {},
        {"global_p_error": 0.038, "p_error": 0.39},
    ],
)
def test_config_torch(model, kwargs):
    """Testing with p_error and global_p_error configs with torch models."""

    input_output_feature = 5
    n_examples = 50

    torch_model = model(input_output_feature, activation_function=nn.ReLU)

    num_inputs = len(signature(torch_model.forward).parameters)

    # Create random input
    inputset = (
        tuple(
            numpy.random.uniform(-100, 100, size=(n_examples, input_output_feature))
            for _ in range(num_inputs)
        )
        if num_inputs > 1
        else numpy.random.uniform(-100, 100, size=(n_examples, input_output_feature))
    )

    if kwargs.get("p_error", None) is not None and kwargs.get("global_p_error", None) is not None:
        with pytest.raises(ValueError) as excinfo:
            compile_torch_model(
                torch_model,
                inputset,
                n_bits={"model_inputs": 2, "model_outputs": 2, "op_inputs": 2, "op_weights": 2},
                use_virtual_lib=False,
                verbose_compilation=True,
                **kwargs
            )

        assert "Please only set one of (p_error, global_p_error) values" in str(excinfo.value)
    else:
        compile_torch_model(
            torch_model,
            inputset,
            n_bits={"model_inputs": 2, "model_outputs": 2, "op_inputs": 2, "op_weights": 2},
            use_virtual_lib=False,
            verbose_compilation=True,
            **kwargs
        )

    # FIXME: https://github.com/zama-ai/concrete-ml-internal/issues/2206
