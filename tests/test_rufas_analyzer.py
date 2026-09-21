from pathlib import Path
import pytest
from tools.rufas_analyzer import parse_arguments, main


def test_analyzer_cli_supports_plot_flag():
    args = parse_arguments(["output/", "--plot"])
    assert args.plot is True
    assert args.output_dir == "output/"


def test_analyzer_cli_plot_flag_default_false():
    args = parse_arguments(["output/"])
    assert args.plot is False


def test_analyzer_cli_invokes_generate_plots_when_flag_present(mocker, tmp_path):
    mock_generate = mocker.patch("tools.rufas_plotter.generate_plots")
    mocker.patch("tools.rufas_analyzer.get_rufas_root", return_value=tmp_path)
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True)
    mocker.patch("tools.rufas_analyzer.validate_analyzer_targets", return_value=out_dir)
    mocker.patch("tools.rufas_analyzer.summarize_output_directory", return_value={})
    mocker.patch("tools.rufas_analyzer.print_markdown_report")
    mocker.patch("sys.argv", ["rufas-analyze", str(out_dir), "--plot"])

    main()

    assert mock_generate.call_count == 1
    call_kwargs = mock_generate.call_args[1]
    assert call_kwargs["preset"] == "executive"
    assert call_kwargs["output_format"] == "both"


def test_analyzer_cli_does_not_invoke_generate_plots_when_flag_absent(mocker, tmp_path):
    mock_generate = mocker.patch("tools.rufas_plotter.generate_plots")
    mocker.patch("tools.rufas_analyzer.get_rufas_root", return_value=tmp_path)
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True)
    mocker.patch("tools.rufas_analyzer.validate_analyzer_targets", return_value=out_dir)
    mocker.patch("tools.rufas_analyzer.summarize_output_directory", return_value={})
    mocker.patch("tools.rufas_analyzer.print_markdown_report")
    mocker.patch("sys.argv", ["rufas-analyze", str(out_dir)])

    main()

    assert mock_generate.call_count == 0
