INFERENCE_TEST_PATH_DONUT = ./donut_model/inference_test.py
INFERENCE_TEST_PATH_QWEN = ./qwen_model/inference_test.py

LABEL_APP_PATH = ./image_labeler/app.py

.PHONY: help
.PHONY: setup
.PHONY: run-inference_test_donut
.PHONY: run-inference_test_qwen
.PHONY: run-labelling

VENV_DIR := .venv
PYTHON := python3
PIP := $(VENV_DIR)/bin/pip
PYTHON_BIN := $(VENV_DIR)/bin/python

help:
# 	@echo "Usage: make [target]"
	@echo ""
	@echo "Make commands:"
	@grep -E '^##' $(MAKEFILE_LIST) | sed 's/## //g' | awk -F ': ' '{printf "  %-25s %s\n", $$1, $$2}'

## setup: Create a local venv and install the project with pip install -e .
setup:
	@echo "Creating virtual environment..."
	@$(PYTHON) -m venv $(VENV_DIR)
	@echo "Installing project dependencies..."
	@$(PIP) install --upgrade pip
	@$(PIP) install -e .
	@echo "Environment ready. Activate it with: source $(VENV_DIR)/bin/activate"

## run-inference_test_donut: Infer the model and test with what is defined in the inference script
run-inference_test_donut:
	@echo "Launching python script..."
	@bash -c "source $(VENV_DIR)/bin/activate && python $(INFERENCE_TEST_PATH_DONUT)"

## run-inference_test_qwen: Infer the model and test with what is defined in the inference script
run-inference_test_qwen:
	@echo "Launching python script..."
	@bash -c "source $(VENV_DIR)/bin/activate && python $(INFERENCE_TEST_PATH_QWEN)"

## run-labelling: launch GUI to help lavel images defined in the configurations
run-labelling:
	@echo "Launching python labelling app..."
	@bash -c "source $(VENV_DIR)/bin/activate && python ${LABEL_APP_PATH}"