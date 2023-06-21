import os
import base64
from PIL import Image
from io import BytesIO
import pytest
from unittest.mock import MagicMock, patch
from superagi.models.resource import Resource
import requests
from superagi.tools.image_generation.stable_diffusion_image_gen import StableDiffusionImageGenTool
from superagi.config.config import get_config
from superagi.helper.resource_helper import ResourceHelper


def mock_get_config(key):
    mock_configs = {
        "STABILITY_API_KEY": "api_key",
        "ENGINE_ID": "engine_id",
        "RESOURCES_OUTPUT_ROOT_DIR": get_config("RESOURCES_OUTPUT_ROOT_DIR"),
    }
    return mock_configs.get(key)


def mock_make_written_file_resource(self, *args, **kwargs):
    resource = Resource()
    resource.id = 1
    resource.path = "workspace/output"
    resource.channel = 'OUTPUT'
    resource.storage_type = 'FILE'
    return resource


def mock_post(url, headers=None, json=None):
    response = MagicMock(status_code=200)
    buffer = BytesIO()
    img = Image.new("RGB", (512, 512), "white")
    img.save(buffer, "PNG")
    buffer.seek(0)
    img_data = buffer.getvalue()
    encoded_image_data = base64.b64encode(img_data).decode()
    response.json = lambda: {
        "artifacts": [
            {"base64": encoded_image_data},
            {"base64": encoded_image_data}
        ]
    }
    return response

@pytest.fixture(autouse=True)
def mock_written_file_resource(monkeypatch):
    monkeypatch.setattr(ResourceHelper, 'make_written_file_resource', mock_make_written_file_resource)


@pytest.fixture
def tool():
    return StableDiffusionImageGenTool()


@pytest.fixture
def temp_dir():
    return get_config("RESOURCES_OUTPUT_ROOT_DIR")


@pytest.fixture
def image_names():
    return ['image1.png', 'image2.png']

@pytest.fixture
def mock_connect_db():
    with patch('superagi.models.db.connect_db') as mock_func:
        yield mock_func


class TestStableDiffusionImageGenTool:

    def test_execute(self, tool, monkeypatch, temp_dir, image_names, mock_connect_db):
        monkeypatch.setattr('superagi.tools.image_generation.stable_diffusion_image_gen.get_config', mock_get_config)
        monkeypatch.setattr(requests, 'post', mock_post)

        prompt = 'Artificial Intelligence'
        height = 512
        width = 512
        num = 2
        steps = 50

        def mock_method(*args, **kwargs):
            return mock_make_written_file_resource(None, *args, **kwargs)

        with patch.object(ResourceHelper, 'make_written_file_resource', mock_method):
            monkeypatch.setattr('superagi.tools.image_generation.stable_diffusion_image_gen.connect_db',
                                mock_connect_db)

            with patch('superagi.tools.image_generation.stable_diffusion_image_gen.StableDiffusionImageGenTool.upload_to_s3',
                       lambda *a, **k: None):
                response = tool._execute(prompt, image_names, width, height, num, steps)

        assert response == "Images downloaded and saved successfully"


    def test_call_stable_diffusion(self, tool, monkeypatch):
        monkeypatch.setattr('superagi.tools.image_generation.stable_diffusion_image_gen.get_config', mock_get_config)
        monkeypatch.setattr(requests, 'post', mock_post)

        api_key = mock_get_config("STABILITY_API_KEY")
        width = 512
        height = 512
        num = 2
        prompt = "Artificial Intelligence"
        steps = 50

        response = tool.call_stable_diffusion(api_key, width, height, num, prompt, steps)
        assert response.status_code == 200
        assert 'artifacts' in response.json()

    def test_upload_to_s3(self, tool, temp_dir, image_names):

        final_img = Image.new("RGB", (512, 512), "white")
        final_path = os.path.join(temp_dir, image_names[0])
        image_format = "PNG"
        file_name = image_names[0]

        mock_session = MagicMock()

        def mock_method(*args, **kwargs):
            return mock_make_written_file_resource(None, *args, **kwargs)

        with patch.object(ResourceHelper, 'make_written_file_resource', mock_method):
            tool.upload_to_s3(final_img, final_path, image_format, file_name, mock_session)

        assert os.path.exists(final_path)

        os.remove(final_path)


    def test_build_file_path(self, tool, monkeypatch, temp_dir, image_names):
        monkeypatch.setattr('superagi.tools.image_generation.stable_diffusion_image_gen.get_config', mock_get_config)

        image = image_names[0]
        root_dir = mock_get_config("RESOURCES_OUTPUT_ROOT_DIR")
        final_path = os.path.join(root_dir, image)

        result = tool.build_file_path(image, root_dir)
        assert os.path.abspath(result) == os.path.abspath(final_path)


if __name__ == "__main__":
    pytest.main()