from unittest.mock import patch
from search_code import get_jobserver_file_shas
from io import StringIO

# test that if file is already in jobserver_sha list it is skipped
@patch("search_code.os.path")
def test_txt_file_is_populated_from_jobserver_pipeline(mock_path):
    file_path = "some\file-path.txt"
    
    mock_path.isfile.return_value = True
    file_content = f"123abc\nabc123\n890xyz"
    mocked_content = StringIO(file_content)
    result = get_jobserver_file_shas()


# test that there are no duplicate file shas

# test that for repos with multiple commit authors, only the most recent is used

# test that the dictionary structures match expected format
