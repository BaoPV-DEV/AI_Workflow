Đặt ở đây file workflow ComfyUI xuất bằng "Save (API Format)".
Trong file dùng {{prompt}}, {{width}}, {{height}}, {{seed}} làm chỗ thay.
Cảnh dùng: {"visual_type": "comfyui", "workflow": "<tên file không đuôi>", "prompt": "..."}
Trỏ config/settings.yaml → visual.comfyui_url sang máy RunPod/Vast khi thuê GPU.
sdxl_image.json là mẫu chuẩn (node gốc của ComfyUI); đổi ckpt_name thành checkpoint bạn có.
Với Flux / Wan 2.1 / LTX-Video: dựng workflow trong ComfyUI, Save (API Format), thay chữ prompt bằng {{prompt}}.
