import pathlib

exec(compile(
    pathlib.Path(__file__).parent.joinpath("app.py").read_text(encoding="utf-8"),
    "app.py",
    "exec",
))
