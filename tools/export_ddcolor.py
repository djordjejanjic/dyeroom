"""Convert DDColor's tiny colourisation model to ONNX for dyeroom/colourise.py.

DDColor (Kang et al., ICCV 2023), code and weights Apache-2.0:
  code     https://github.com/piddnad/DDColor (tested at 2adb63f2656ac41cbdf7b894cddd94121a3faf13)
  weights  https://huggingface.co/piddnad/ddcolor_paper_tiny

Needs torch, onnx, onnxruntime, huggingface_hub and a checkout of the DDColor repository:
  git clone https://github.com/piddnad/DDColor && git -C DDColor checkout 2adb63f
  python tools/export_ddcolor.py DDColor dyeroom/data/cache/ddcolor_paper_tiny.onnx

The server then needs only onnxruntime. The export is checked against PyTorch's own output.
"""
import sys
from pathlib import Path

import numpy as np
import onnxruntime
import torch
from huggingface_hub import hf_hub_download

SIZE = 512


def main(repo, out):
    sys.path.insert(0, str(Path(repo).resolve()))
    from basicsr.archs.ddcolor_arch import DDColor  # the repository's own architecture

    model = DDColor(encoder_name="convnext-t", decoder_name="MultiScaleColorDecoder", input_size=[SIZE, SIZE],
                    num_output_channels=2, last_norm="Spectral", do_normalize=False,
                    num_queries=100, num_scales=3, dec_layers=9)
    weights = torch.load(hf_hub_download("piddnad/ddcolor_paper_tiny", "pytorch_model.bin"), map_location="cpu")
    state = weights.get("params", weights)
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        raise SystemExit(f"weights do not fit the model, missing: {missing[:5]}")
    model.eval()

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    probe = torch.rand(1, 3, SIZE, SIZE)
    torch.onnx.export(model, probe, out, opset_version=17, input_names=["input"], output_names=["ab"],
                      dynamo=False)
    with torch.no_grad():
        expected = model(probe).numpy()
    got = onnxruntime.InferenceSession(out, providers=["CPUExecutionProvider"]).run(None, {"input": probe.numpy()})[0]
    error = float(np.abs(got - expected).max())
    print(f"{out}: {Path(out).stat().st_size / 1e6:.0f} MB, largest difference from PyTorch {error:.4f} (a*b* units)")
    if error > 0.5:
        raise SystemExit("the ONNX model does not match PyTorch")


if __name__ == "__main__":
    main(*sys.argv[1:3])
