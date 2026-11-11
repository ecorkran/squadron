from unittest.mock import patch

import fixpkg.mod


def test_execute_passes_a_timeout():
    with patch("fixpkg.mod.run") as fake:
        fixpkg.mod.execute(["echo"])
    assert fake.call_args.kwargs.get("timeout") == 5
