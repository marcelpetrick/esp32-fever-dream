#!/usr/bin/env python3
"""Train and export a tiny fixed-display digit classifier."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

CLASSES = tuple("0123456789")
TARGET_SHAPE = (32, 24, 1)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the TinyML digit classifier.")
    parser.add_argument("--digit-labels", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--firmware-header",
        type=Path,
        help="Optional firmware C header output; omit during tuning.",
    )
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=173)
    parser.add_argument("--real-weight", type=float, default=1.0)
    parser.add_argument("--early-stopping-patience", type=int, default=4)
    parser.add_argument(
        "--qualify-test",
        action="store_true",
        help="Evaluate the frozen test split after validation qualification.",
    )
    return parser.parse_args(list(argv))


def require_tensorflow():
    try:
        import tensorflow as tf  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "TensorFlow is required to train/export TFLite. Run "
            "`./scripts/setup_ml_env.sh` and then `. .venv-ml/bin/activate`, "
            f"or use a Python 3.11/3.12 environment with tensorflow installed. Import failed: {exc}"
        ) from exc
    return tf


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        return list(reader)


def validate_source_splits(rows: list[dict[str, str]]) -> None:
    synthetic_heldout = [
        row for row in rows if row.get("source") == "synthetic" and row["split"] != "train"
    ]
    if synthetic_heldout:
        raise ValueError("synthetic rows are forbidden in validation and test splits")
    non_real_heldout = [
        row
        for row in rows
        if row["split"] in {"validation", "test"} and row.get("source", "real") != "real"
    ]
    if non_real_heldout:
        raise ValueError("validation and test must contain real crops only")


def load_split(
    rows: list[dict[str, str]], split: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_values: list[np.ndarray] = []
    y_values: list[int] = []
    real_values: list[bool] = []
    for row in rows:
        if row["split"] != split:
            continue
        image = Image.open(row["image_path"]).convert("L").resize((24, 32))
        x_values.append(np.asarray(image, dtype=np.float32) / 255.0)
        y_values.append(CLASSES.index(row["label"]))
        real_values.append(row.get("source", "real") == "real")
    if not x_values:
        raise ValueError(f"no rows for split {split}")
    x = np.asarray(x_values, dtype=np.float32).reshape((-1,) + TARGET_SHAPE)
    y = np.asarray(y_values, dtype=np.int64)
    is_real = np.asarray(real_values, dtype=np.bool_)
    return x, y, is_real


def build_model(tf):
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=TARGET_SHAPE),
            tf.keras.layers.Conv2D(16, 3, activation="relu", padding="same"),
            tf.keras.layers.MaxPooling2D(),
            tf.keras.layers.Conv2D(32, 3, activation="relu", padding="same"),
            tf.keras.layers.MaxPooling2D(),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(64, activation="relu"),
            tf.keras.layers.Dense(len(CLASSES), activation="softmax"),
        ]
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def representative_dataset(x_train: np.ndarray):
    for sample in x_train[: min(128, len(x_train))]:
        yield [sample.reshape((1,) + TARGET_SHAPE).astype(np.float32)]


def write_c_array(tflite_path: Path, output_path: Path) -> None:
    data = tflite_path.read_bytes()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "#pragma once",
        "",
        "#include <cstddef>",
        "#include <cstdint>",
        "",
        "namespace fever::generated {",
        f"inline constexpr std::size_t kDigitClassifierModelSize = {len(data)}U;",
        "alignas(16) inline constexpr std::uint8_t kDigitClassifierModel[] = {",
    ]
    for index in range(0, len(data), 12):
        chunk = ", ".join(f"0x{byte:02x}" for byte in data[index : index + 12])
        lines.append(f"    {chunk},")
    lines.extend(["};", "}  // namespace fever::generated", ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> list[list[int]]:
    matrix = [[0 for _ in CLASSES] for _ in CLASSES]
    for truth, pred in zip(y_true, y_pred, strict=True):
        matrix[int(truth)][int(pred)] += 1
    return matrix


def predict_tflite(model_path: Path, x_values: np.ndarray, tf) -> np.ndarray:
    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    scale, zero_point = input_detail["quantization"]
    if scale <= 0:
        raise ValueError("TFLite input tensor has invalid quantization scale")
    predictions: list[int] = []
    for sample in x_values:
        quantized = np.rint(sample / scale + zero_point)
        quantized = np.clip(quantized, -128, 127).astype(np.int8)[None, ...]
        interpreter.set_tensor(input_detail["index"], quantized)
        interpreter.invoke()
        predictions.append(int(np.argmax(interpreter.get_tensor(output_detail["index"])[0])))
    return np.asarray(predictions, dtype=np.int64)


def accuracy_report(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, object]:
    matrix = confusion_matrix(y_true, y_pred)
    per_digit = {}
    for index, digit in enumerate(CLASSES):
        total = int(np.sum(y_true == index))
        correct = int(np.sum((y_true == index) & (y_pred == index)))
        per_digit[digit] = {
            "correct": correct,
            "total": total,
            "accuracy": (correct / total) if total else None,
        }
    return {
        "rows": int(len(y_true)),
        "accuracy": float(np.mean(y_true == y_pred)),
        "per_digit": per_digit,
        "confusion_matrix": matrix,
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.real_weight <= 0:
        raise ValueError("--real-weight must be positive")
    tf = require_tensorflow()
    tf.keras.utils.set_random_seed(args.seed)

    rows = read_rows(args.digit_labels)
    validate_source_splits(rows)
    x_train, y_train, train_is_real = load_split(rows, "train")
    x_validation, y_validation, validation_is_real = load_split(rows, "validation")
    if not np.all(validation_is_real):
        raise ValueError("validation must contain real crops only")
    x_test = y_test = test_is_real = None
    if args.qualify_test:
        x_test, y_test, test_is_real = load_split(rows, "test")
        if not np.all(test_is_real):
            raise ValueError("test must contain real crops only")

    model = build_model(tf)

    # Per-class inverse-frequency weights merged into sample weights so Keras
    # doesn't receive both class_weight and sample_weight simultaneously.
    # Digit '0' is 32% of crops (leading-zero CO2/HCHO/TVOC encoding), which
    # without balancing biases the model towards predicting '0'.
    class_counts = np.bincount(y_train, minlength=len(CLASSES)).astype(np.float32)
    class_counts = np.where(class_counts == 0, 1.0, class_counts)
    class_freq_weight = (class_counts.sum() / (len(CLASSES) * class_counts)).astype(np.float32)
    sample_weight = (
        np.where(train_is_real, args.real_weight, 1.0) * class_freq_weight[y_train]
    ).astype(np.float32)

    history = model.fit(
        x_train,
        y_train,
        sample_weight=sample_weight,
        validation_data=(x_validation, y_validation),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=args.early_stopping_patience,
                restore_best_weights=True,
            )
        ],
        verbose=2,
    )

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    keras_path = output_dir / "digit_classifier.keras"
    tflite_path = output_dir / "digit_classifier_int8.tflite"
    model.save(keras_path)

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = lambda: representative_dataset(x_train)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    tflite_path.write_bytes(converter.convert())
    if args.firmware_header is not None:
        write_c_array(tflite_path, args.firmware_header)

    validation_predictions = predict_tflite(tflite_path, x_validation, tf)
    validation_report = accuracy_report(y_validation, validation_predictions)
    test_report = None
    if args.qualify_test:
        assert x_test is not None and y_test is not None
        test_report = accuracy_report(y_test, predict_tflite(tflite_path, x_test, tf))
    matrix = validation_report["confusion_matrix"]
    report = {
        "classes": CLASSES,
        "digit_labels": str(args.digit_labels),
        "epochs": args.epochs,
        "history": {key: [float(value) for value in values] for key, values in history.history.items()},
        "seed": args.seed,
        "real_weight": args.real_weight,
        "validation_real_tflite": validation_report,
        "test_real_tflite": test_report,
        "test_was_qualified": args.qualify_test,
        "tflite_model": str(tflite_path),
        "tflite_size_bytes": tflite_path.stat().st_size,
        "firmware_header": str(args.firmware_header) if args.firmware_header else None,
        "confusion_matrix": matrix,
        "warning": "Frozen test metrics are absent unless --qualify-test is explicitly supplied.",
    }
    (output_dir / "digit_classifier_eval.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "confusion_matrix.csv").open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["truth\\pred", *CLASSES])
        for digit, row in zip(CLASSES, matrix, strict=True):
            writer.writerow([digit, *row])
    print(f"[INFO] validation_real_tflite_accuracy={validation_report['accuracy']:.4f}")
    print(f"[INFO] wrote {tflite_path}")
    if args.firmware_header is not None:
        print(f"[INFO] wrote {args.firmware_header}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
