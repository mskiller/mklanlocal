from __future__ import annotations

import json
from datetime import datetime, timezone

from media_indexer_backend.models.enums import MediaType
from media_indexer_backend.services.metadata import (
    build_search_text,
    build_tags,
    compute_prompt_tag_similarity,
    compute_prompt_tag_overlap,
    hamming_distance,
    normalized_metadata_for_api,
    normalize_metadata,
    should_reextract_metadata,
)


def test_normalize_image_metadata_extracts_common_fields() -> None:
    normalized = normalize_metadata(
        media_type=MediaType.IMAGE,
        exif={
            "ImageWidth": 4032,
            "ImageHeight": 3024,
            "Make": "Sony",
            "Model": "ILCE-7M4",
            "DateTimeOriginal": "2025-04-10T14:20:00+00:00",
        },
        ffprobe=None,
    )

    assert normalized["width"] == 4032
    assert normalized["height"] == 3024
    assert normalized["camera_make"] == "Sony"
    assert normalized["camera_model"] == "ILCE-7M4"
    assert normalized["created_at"].startswith("2025-04-10T14:20:00")


def test_build_tags_and_search_text_are_search_friendly() -> None:
    normalized = {
        "camera_make": "Canon",
        "camera_model": "EOS R6",
        "lens": "24-70mm",
        "created_at": "2024-07-11T08:00:00+00:00",
        "media_type": "image",
        "width": 6000,
        "height": 4000,
    }
    tags = build_tags(normalized, {"Keywords": ["Sunset", "Travel"]})
    search_text = build_search_text("sunset.jpg", "Trips/Italy/sunset.jpg", normalized, tags)

    assert "camera:canon" in tags
    assert "travel" in tags
    assert "Trips/Italy/sunset.jpg" in search_text
    assert "EOS R6" in search_text


def test_normalize_metadata_extracts_automatic1111_prompt_fields() -> None:
    normalized = normalize_metadata(
        media_type=MediaType.IMAGE,
        exif={
            "Parameters": (
                "masterpiece, cinematic lighting, red dress\n"
                "Negative prompt: lowres, blurry, bad hands\n"
                "Steps: 28, Sampler: DPM++ 2M, CFG scale: 7, Seed: 1234"
            )
        },
        ffprobe=None,
    )

    tags = build_tags(normalized)
    search_text = build_search_text("a1111.png", "gens/a1111.png", normalized, tags)

    assert normalized["generator"] == "automatic1111"
    assert normalized["prompt"] == "masterpiece, cinematic lighting, red dress"
    assert normalized["negative_prompt"] == "lowres, blurry, bad hands"
    assert normalized["workflow_format"] == "automatic1111_parameters"
    assert normalized["steps"] == 28
    assert normalized["cfg_scale"] == 7.0
    assert normalized["seed"] == 1234
    assert normalized["sampler_name"] == "DPM++ 2M"
    assert "generator:automatic1111" in tags
    assert "cinematic_lighting" in tags
    assert "bad hands" not in tags
    assert "red dress" in search_text


def test_normalize_metadata_extracts_comfyui_prompt_and_prompt_tags() -> None:
    prompt_graph = {
        "10": {
            "class_type": "ImpactWildcardProcessor",
            "inputs": {
                "populated_text": "masterpiece, cinematic photo, blue eyes, freckles",
            },
        },
        "20": {
            "class_type": "ImpactWildcardProcessor",
            "inputs": {
                "populated_text": "lowres, blurry, jpeg artifacts",
            },
        },
        "30": {
            "class_type": "Text Concatenate (JPS)",
            "inputs": {
                "text1": ["10", 0],
                "text2": "golden hour",
                "text3": "detailed skin",
            },
        },
        "40": {
            "class_type": "ComfySwitchNode",
            "inputs": {
                "switch": False,
                "on_true": ["30", 0],
                "on_false": ["10", 0],
            },
        },
        "11": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode (Prompt)"},
            "inputs": {
                "text": ["40", 0],
            },
        },
        "12": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode (Negative Prompt)"},
            "inputs": {
                "text": ["20", 0],
            },
        },
        "13": {
            "class_type": "KSampler",
            "inputs": {
                "positive": ["11", 0],
                "negative": ["12", 0],
                "seed": 987654,
                "steps": 30,
                "cfg": 6.5,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
            },
        },
        "14": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "dreamshaper.safetensors",
            },
        },
        "15": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "vae-ft-mse-840000-ema-pruned.safetensors",
            },
        },
        "16": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "detail_tweaker.safetensors",
            },
        },
    }
    workflow = {
        "nodes": [
            {
                "id": 10,
                "type": "ImpactWildcardProcessor",
                "widgets_values": [],
                "inputs": {
                    "populated_text": "masterpiece, cinematic photo, blue eyes, freckles",
                },
            },
            {
                "id": 40,
                "type": "ComfySwitchNode",
                "widgets_values": [False],
                "inputs": {"switch": False},
            },
        ]
    }

    normalized = normalize_metadata(
        media_type=MediaType.IMAGE,
        exif={
            "Prompt": json.dumps(prompt_graph),
            "Workflow": json.dumps(workflow),
        },
        ffprobe=None,
    )

    tags = build_tags(normalized)
    search_text = build_search_text("comfy.png", "gens/comfy.png", normalized, tags)

    assert normalized["generator"] == "comfyui"
    assert normalized["prompt"] == "masterpiece, cinematic photo, blue eyes, freckles"
    assert normalized["negative_prompt"] == "lowres, blurry, jpeg artifacts"
    assert normalized["workflow_text"] is not None
    assert "True" not in normalized["workflow_text"]
    assert normalized["seed"] == 987654
    assert normalized["steps"] == 30
    assert normalized["cfg_scale"] == 6.5
    assert normalized["sampler_name"] == "dpmpp_2m"
    assert normalized["scheduler"] == "karras"
    assert normalized["checkpoint"] == "dreamshaper.safetensors"
    assert normalized["vae"] == "vae-ft-mse-840000-ema-pruned.safetensors"
    assert normalized["loras"] == ["detail_tweaker.safetensors"]
    assert "freckles" in normalized["prompt_tags"]
    assert "generator:comfyui" in tags
    assert "cinematic_photo" in tags
    assert "sampler:dpmpp_2m" in tags
    assert "lora:detail_tweaker.safetensors" in tags
    assert "jpeg artifacts" in search_text


def test_normalize_metadata_prefers_main_comfyui_prompt_branch_over_noisy_secondary_samplers() -> None:
    prompt_graph = {
        "26": {
            "class_type": "ImpactWildcardProcessor",
            "_meta": {"title": "Negative"},
            "inputs": {
                "wildcard_text": "score_5, score_4, text, watermark",
                "populated_text": "lowres, blurry, bad anatomy",
            },
        },
        "58": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode (Prompt)"},
            "inputs": {"text": ["26", 0]},
        },
        "1300": {
            "class_type": "ImpactWildcardProcessor",
            "_meta": {"title": "Positive"},
            "inputs": {
                "wildcard_text": "{__wildcard/style__}",
                "populated_text": "(masterpiece, 1girl, blue eyes, freckles, cinematic lighting)",
            },
        },
        "59": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode (Prompt)"},
            "inputs": {"text": ["1300", 0]},
        },
        "1301": {
            "class_type": "ImpactStringSelector",
            "_meta": {"title": "Huge selector"},
            "inputs": {
                "select": 999999,
                "strings": "bad option one\nbad option two\nbad option three",
            },
        },
        "1310": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode (Prompt)"},
            "inputs": {"text": ["1301", 0]},
        },
        "85": {
            "class_type": "KSampler (Efficient)",
            "_meta": {"title": "KSampler (Efficient)"},
            "inputs": {
                "positive": ["59", 0],
                "negative": ["58", 0],
                "sampler_name": "lcm",
                "scheduler": "kl_optimal",
            },
        },
        "86": {
            "class_type": "Detailer Sampler",
            "_meta": {"title": "Detailer Sampler"},
            "inputs": {
                "positive": ["1310", 0],
                "negative": ["58", 0],
            },
        },
        "89": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "dreamshaper.safetensors"},
        },
    }

    normalized = normalize_metadata(
        media_type=MediaType.IMAGE,
        exif={"Prompt": json.dumps(prompt_graph), "Workflow": json.dumps({"nodes": []})},
        ffprobe=None,
    )

    assert normalized["prompt"] == "(masterpiece, 1girl, blue eyes, freckles, cinematic lighting)"
    assert normalized["negative_prompt"] == "lowres, blurry, bad anatomy\nscore_5, score_4, text, watermark"
    assert "bad option one" not in (normalized["prompt"] or "")
    assert "__wildcard/style__" not in (normalized["prompt"] or "")
    assert normalized["workflow_text"] is not None
    assert "999999" not in normalized["workflow_text"]
    assert "dreamshaper.safetensors" in normalized["workflow_text"]


def test_prompt_tag_overlap_tracks_shared_and_unique_tags() -> None:
    overlap, shared, left_only, right_only = compute_prompt_tag_overlap(
        {"prompt_tags": ["cinematic lighting", "freckles", "solo"]},
        {"prompt_tags": ["freckles", "blue eyes", "solo"]},
    )

    assert overlap == 2
    assert shared == ["freckles", "solo"]
    assert left_only == ["cinematic_lighting"]
    assert right_only == ["blue_eyes"]


def test_prompt_tag_similarity_uses_jaccard_score() -> None:
    score, shared, left_only, right_only = compute_prompt_tag_similarity(
        {"prompt_tags": ["freckles", "solo", "cinematic_lighting"]},
        {"prompt_tags": ["freckles", "solo", "blue_eyes"]},
    )

    assert score == 0.5
    assert shared == ["freckles", "solo"]
    assert left_only == ["cinematic_lighting"]
    assert right_only == ["blue_eyes"]


def test_normalized_metadata_for_api_reextracts_clean_danbooru_tags_from_prompt() -> None:
    normalized = normalized_metadata_for_api(
        {
            "metadata_version": 5,
            "prompt": (
                "(Masterpiece, absurdres, highres, painting_(medium), oil_painting_(medium), parody:1.2), "
                "(fine_art_parody, kanagawa_okinami_ura:1.4), "
                "(easel, canvas_(object), painting_(object):1.2), "
                "(1girl, mature_female, aged_up, shiina_yuika_(nijisanji), medium_breasts:1.2), "
                "(absurdly_detailed_composition:1.2)."
            ),
            "prompt_tags": ["Masterpiece", "parody:1.2)", "medium breasts", "absurdly_detailed_composition:1.2)"],
        }
    )

    assert normalized["prompt_tags"] == [
        "masterpiece",
        "absurdres",
        "highres",
        "painting_(medium)",
        "oil_painting_(medium)",
        "parody",
        "fine_art_parody",
        "kanagawa_okinami_ura",
        "easel",
        "canvas_(object)",
        "painting_(object)",
        "1girl",
        "mature_female",
        "aged_up",
        "shiina_yuika_(nijisanji)",
        "medium_breasts",
        "absurdly_detailed_composition",
    ]
    assert normalized["prompt_tag_string"] is not None
    assert "medium_breasts" in normalized["prompt_tag_string"]
    assert "parody:1.2" not in normalized["prompt_tag_string"]


def test_should_reextract_metadata_when_version_is_stale_even_if_file_is_unchanged() -> None:
    modified_at = datetime(2026, 4, 11, 8, 30, tzinfo=timezone.utc)

    assert should_reextract_metadata(
        existing_size_bytes=1024,
        existing_modified_at=modified_at,
        existing_normalized_json={"metadata_version": 2},
        file_size_bytes=1024,
        file_modified_at=modified_at,
    )

    assert not should_reextract_metadata(
        existing_size_bytes=1024,
        existing_modified_at=modified_at,
        existing_normalized_json={"metadata_version": 6},
        file_size_bytes=1024,
        file_modified_at=modified_at,
    )


def test_hamming_distance_handles_hex_hashes() -> None:
    assert hamming_distance("ff00", "ff00") == 0
    assert hamming_distance("ff00", "00ff") == 16
