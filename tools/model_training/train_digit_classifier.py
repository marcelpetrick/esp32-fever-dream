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
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=173)
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


def load_split(rows: list[dict[str, str]], split: str) -> tuple[np.ndarray, np.ndarray]:
    x_values: list[np.ndarray] = []
    y_values: list[int] = []
    for row in rows:
        if row["split"] != split:
            continue
        image = Image.open(row["image_path"]).convert("L").resize((24, 32))
        x_values.append(np.asarray(image, dtype=np.float32) / 255.0)
        y_values.append(CLASSES.index(row["label"]))
    if not x_values:
        raise ValueError(f"no rows for split {split}")
    x = np.asarray(x_values, dtype=np.float32).reshape((-1,) + TARGET_SHAPE)
    y = np.asarray(y_values, dtype=np.int64)
    return x, y


def build_model(tf):
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=TARGET_SHAPE),
            tf.keras.layers.Conv2D(8, 3, activation="relu", padding="same"),
            tf.keras.layers.MaxPooling2D(),
            tf.keras.layers.Conv2D(16, 3, activation="relu", padding="same"),
            tf.keras.layers.MaxPooling2D(),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(32, activation="relu"),
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


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    tf = require_tensorflow()
    tf.keras.utils.set_random_seed(args.seed)

    rows = read_rows(args.digit_labels)
    x_train, y_train = load_split(rows, "train")
    x_validation, y_validation = load_split(rows, "validation")
    x_test, y_test = load_split(rows, "test")

    model = build_model(tf)
    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_validation, y_validation),
        epochs=args.epochs,
        batch_size=args.batch_size,
        verbose=2,
    )
    test_loss, test_accuracy = model.evaluate(x_test, y_test, verbose=0)

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
    write_c_array(tflite_path, Path("firmware/generated/digit_classifier_model.h"))

    predictions = np.argmax(model.predict(x_test, verbose=0), axis=1)
    matrix = confusion_matrix(y_test, predictions)
    report = {
        "classes": CLASSES,
        "digit_labels": str(args.digit_labels),
        "epochs": args.epochs,
        "history": {key: [float(value) for value in values] for key, values in history.history.items()},
        "test_loss": float(test_loss),
        "test_accuracy": float(test_accuracy),
        "tflite_model": str(tflite_path),
        "tflite_size_bytes": tflite_path.stat().st_size,
        "firmware_header": "firmware/generated/digit_classifier_model.h",
        "confusion_matrix": matrix,
        "warning": "Prototype includes synthetic test rows; final acceptance still requires diverse held-out real captures.",
    }
    (output_dir / "digit_classifier_eval.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "confusion_matrix.csv").open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["truth\\pred", *CLASSES])
        for digit, row in zip(CLASSES, matrix, strict=True):
            writer.writerow([digit, *row])
    print(f"[INFO] test_accuracy={test_accuracy:.4f}")
    print(f"[INFO] wrote {tflite_path}")
    print("[INFO] wrote firmware/generated/digit_classifier_model.h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
