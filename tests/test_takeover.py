import os
import tempfile
import unittest
from pathlib import Path

from witchy import takeover


class OwnerTest(unittest.TestCase):
    def test_lines_that_own_the_prompt(self):
        cases = {
            "starship init fish | source": "starship init",
            "    starship init fish | source": "starship init",
            "if type -q starship; starship init fish | source; end": "starship init",
            "oh-my-posh init fish --config ~/theme.json | source": "oh-my-posh init",
            "oh-my-posh --init --shell fish --config ~/theme.json | source": "oh-my-posh init",
            "set -g tide_pwd_icon x": "set -g tide_pwd_icon",
            "set -gx tide_time_color 5F8787": "set -g tide_time_color",
            "set -xg tide_time_color 5F8787": "set -g tide_time_color",
            "set -g -x tide_time_color 5F8787": "set -g tide_time_color",
            "set --global tide_character_icon '>'": "set -g tide_character_icon",
            "test -n x; and set -g tide_git_icon y": "set -g tide_git_icon",
            "set -q tide_x; or set -g tide_x y": "set -g tide_x",
        }
        for line, what in cases.items():
            with self.subTest(line=line):
                self.assertEqual(takeover.owner(line), what)

    def test_lines_that_do_not(self):
        for line in ("# starship init fish | source", "   # set -g tide_x y",
                     "# witchy-disabled: starship init fish | source", "set -U tide_pwd_icon x",
                     "set -l tide_pwd_icon x", "set tide_pwd_icon x", "set -q -g tide_pwd_icon",
                     "set -e -g tide_pwd_icon", "set --erase --global tide_pwd_icon", "set -g _tide_left_items",
                     "set -g fish_greeting", "echo starship", "set -g offset_tide_x 1", "",
                     "echo hi  # starship init fish", "abbr -a ss 'starship init fish | source'",
                     'echo "set -g tide_x y"', "echo a#b; echo b # oh-my-posh init fish"):
            with self.subTest(line=line):
                self.assertIsNone(takeover.owner(line))


class ScanTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name) / "fish"
        (self.folder / "conf.d").mkdir(parents=True)

    def write(self, name, data):
        path = self.folder / name
        path.write_bytes(data)
        return path

    def test_finds_each_owner_and_disables_only_those_lines(self):
        config = self.write("config.fish", b"if status is-interactive\n    starship init fish | source\nend\n"
                                           b"set -g tide_pwd_icon x\n")
        mine = self.write("conf.d/mine.fish", b"oh-my-posh init fish | source\n")
        found = takeover.scan(self.folder)
        self.assertEqual(found.lines, [takeover.Line(config, 2, "starship init"),
                                       takeover.Line(config, 4, "set -g tide_pwd_icon"),
                                       takeover.Line(mine, 1, "oh-my-posh init")])
        self.assertEqual(found.blockers, [])
        self.assertEqual([(change.path, change.after) for change in found.changes], [
            (config, b"if status is-interactive\n# witchy-disabled:     starship init fish | source\nend\n"
                     b"# witchy-disabled: set -g tide_pwd_icon x\n"),
            (mine, b"# witchy-disabled: oh-my-posh init fish | source\n")])
        self.assertEqual(found.changes[0].before, config.read_bytes())

    def test_a_second_run_finds_nothing(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.write("config.fish", takeover.scan(self.folder).changes[0].after)
        found = takeover.scan(self.folder)
        self.assertEqual((found.lines, found.blockers, found.changes), ([], [], []))
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")

    def test_a_line_turned_back_on_is_found_again(self):
        self.write("config.fish", b"# witchy-disabled: starship init fish | source\nstarship init fish | source\n")
        self.assertEqual([line.number for line in takeover.scan(self.folder).lines], [2])

    def test_a_fish_prompt_function_blocks_the_takeover(self):
        self.write("config.fish", b"set -g tide_x y\nfunction fish_prompt --description 'mine'\n    echo '> '\nend\n"
                                  b"function fish_prompt_extra\nend\n")
        found = takeover.scan(self.folder)
        self.assertEqual(found.blockers, ["config.fish defines fish_prompt at line 2; remove that function"])

    def test_a_continued_line_blocks_the_takeover(self):
        self.write("config.fish", b"set -g tide_left_prompt_items pwd \\\n    git\n")
        self.write("conf.d/mine.fish", b"echo one \\\nstarship init fish | source\n")
        found = takeover.scan(self.folder)
        self.assertEqual(found.blockers, [
            "config.fish line 1 is continued over several lines; disable it yourself",
            "conf.d/mine.fish line 2 is continued over several lines; disable it yourself"])

    def test_a_symlinked_file_is_never_edited(self):
        dotfiles = Path(self.folder.parent) / "dotfiles.fish"
        dotfiles.write_bytes(b"starship init fish | source\nset -g tide_x y\n")
        os.symlink(dotfiles, self.folder / "config.fish")
        found = takeover.scan(self.folder)
        self.assertEqual(found.blockers, [f"config.fish is a symlink to {dotfiles}; disable lines 1, 2 there yourself"])
        self.assertEqual(found.changes, [])

    def test_a_symlinked_file_with_nothing_to_take_over_is_fine(self):
        dotfiles = Path(self.folder.parent) / "dotfiles.fish"
        dotfiles.write_bytes(b"alias ll 'ls -l'\n")
        os.symlink(dotfiles, self.folder / "config.fish")
        self.assertEqual(takeover.scan(self.folder).blockers, [])

    def test_line_endings_and_bytes_are_kept(self):
        data = b"echo \xff\xfe\r\nstarship init fish | source\r\nset -g tide_x \xe9\r\n"
        self.write("config.fish", data)
        change = takeover.scan(self.folder).changes[0]
        self.assertEqual(change.after, b"echo \xff\xfe\r\n# witchy-disabled: starship init fish | source\r\n"
                                       b"# witchy-disabled: set -g tide_x \xe9\r\n")
        self.assertEqual(takeover.enable(change.after), data)

    def test_a_missing_or_empty_config_has_nothing_to_take_over(self):
        self.assertEqual(takeover.scan(self.folder / "nowhere"), takeover.Scan())
        self.assertEqual(takeover.scan(self.folder), takeover.Scan())
        self.write("config.fish", b"")
        self.assertEqual(takeover.scan(self.folder), takeover.Scan())

    def test_files_it_must_leave_are_skipped(self):
        witchy = self.write("conf.d/witchy.fish", b"set -g tide_character_color FFB86B\n")
        fisher = self.write("conf.d/_tide_init.fish", b"set -g tide_x y\n")
        self.write("conf.d/notes.txt", b"starship init fish | source\n")
        self.assertEqual(takeover.scan(self.folder, {witchy, fisher}), takeover.Scan())

    def blockers(self, data, name="config.fish"):
        self.write(name, data)
        found = takeover.scan(self.folder)
        self.assertEqual(found.changes, [])
        return found.blockers

    def test_a_line_that_opens_or_closes_a_block_blocks_the_takeover(self):
        message = "config.fish line {} opens or closes a block; disable it yourself"
        for data, number in ((b"if status is-interactive\n    starship init fish | source; end\n", 2),
                             (b"if command -q starship; starship init fish | source\nend\n", 1),
                             (b"if x\n  echo a\nelse; set -g tide_x y\nend\n", 3),
                             (b"for i in 1\n  set -g tide_x $i; end\n", 2)):
            with self.subTest(data=data):
                self.assertEqual(self.blockers(data), [message.format(number)])

    def test_a_balanced_one_line_block_is_disabled_whole(self):
        self.write("config.fish", b"if type -q starship; starship init fish | source; end\n")
        found = takeover.scan(self.folder)
        self.assertEqual(found.blockers, [])
        self.assertEqual(found.changes[0].after,
                         b"# witchy-disabled: if type -q starship; starship init fish | source; end\n")

    def test_a_command_chained_over_lines_blocks_the_takeover(self):
        self.assertEqual(self.blockers(b"type -q starship &&\n    starship init fish | source\necho after\n"),
                         ["config.fish line 2 is continued over several lines; disable it yourself"])
        for ending in (b"\\", b"&&", b"||", b"|", b"&& \r"):
            with self.subTest(ending=ending):
                self.assertEqual(self.blockers(b"starship init fish | source " + ending + b"\necho after\n"),
                                 ["config.fish line 1 is continued over several lines; disable it yourself"])

    def test_a_comment_ending_in_an_operator_does_not_continue(self):
        self.write("config.fish", b"echo a # b &&\nstarship init fish | source\n")
        self.assertEqual(len(takeover.scan(self.folder).changes), 1)

    def test_a_symlinked_folder_is_never_edited(self):
        elsewhere = Path(self.folder.parent) / "dotfiles"
        (elsewhere / "conf.d").mkdir(parents=True)
        (elsewhere / "config.fish").write_bytes(b"starship init fish | source\n")
        (elsewhere / "conf.d" / "mine.fish").write_bytes(b"set -g tide_x y\n")
        link = Path(self.folder.parent) / "link"
        os.symlink(elsewhere, link)
        found = takeover.scan(link)
        self.assertEqual(found.blockers, [
            f"config.fish is a symlink to {elsewhere.resolve() / 'config.fish'}; disable line 1 there yourself",
            f"conf.d/mine.fish is a symlink to {elsewhere.resolve() / 'conf.d' / 'mine.fish'}; "
            "disable line 1 there yourself"])
        self.assertEqual(found.changes, [])

    def test_a_symlinked_conf_d_is_never_edited(self):
        elsewhere = Path(self.folder.parent) / "confd"
        elsewhere.mkdir()
        (elsewhere / "mine.fish").write_bytes(b"set -g tide_x y\n")
        (self.folder / "conf.d").rmdir()
        os.symlink(elsewhere, self.folder / "conf.d")
        found = takeover.scan(self.folder)
        self.assertEqual(found.blockers, [f"conf.d/mine.fish is a symlink to {elsewhere.resolve() / 'mine.fish'}; "
                                          "disable line 1 there yourself"])
        self.assertEqual(found.changes, [])

    def test_skipped_files_are_matched_by_resolved_path(self):
        self.write("conf.d/witchy.fish", b"set -g tide_character_color FFB86B\n")
        alias = Path(self.folder.parent) / "alias"
        os.symlink(self.folder, alias)
        self.assertEqual(takeover.scan(self.folder, {alias / "conf.d" / "witchy.fish"}), takeover.Scan())
        self.assertEqual(takeover.scan(self.folder, {alias / "conf.d" / "other.fish"}).changes[0].path.name,
                         "witchy.fish")

    def test_a_line_fish_cannot_read_once_disabled_blocks_the_takeover(self):
        # A stand-in for `fish --no-execute`: an open "(" left without its line no longer parses.
        def parses(data):
            checked.append(data)
            return b"# witchy-disabled: set -g tide_pwd_color (" not in data

        checked = []
        self.write("config.fish", b"starship init fish | source\nset -g tide_pwd_color (\n    echo 123\n)\n")
        found = takeover.scan(self.folder, parses=parses)
        self.assertEqual(found.blockers, [
            "config.fish line 2 is part of a command or string over several lines (fish could not read the file "
            "with it disabled); disable it yourself"])
        self.assertEqual(found.lines, [takeover.Line(self.folder / "config.fish", 1, "starship init")])
        self.assertEqual(checked[:2], [b"# witchy-disabled: starship init fish | source\n"
                                       b"# witchy-disabled: set -g tide_pwd_color (\n    echo 123\n)\n",
                                       b"starship init fish | source\nset -g tide_pwd_color (\n    echo 123\n)\n"])

    def test_a_file_fish_reads_once_disabled_is_checked_once(self):
        checked = []
        self.write("config.fish", b"starship init fish | source\n")
        found = takeover.scan(self.folder, parses=lambda data: checked.append(data) or True)
        self.assertEqual((found.blockers, len(found.changes)), ([], 1))
        self.assertEqual(checked, [b"# witchy-disabled: starship init fish | source\n"])

    def test_a_file_fish_could_not_read_before_is_left_to_the_other_checks(self):
        self.write("config.fish", b"starship init fish | source\nend\n")
        found = takeover.scan(self.folder, parses=lambda data: False)
        self.assertEqual((found.blockers, len(found.changes)), ([], 1))

    def test_lines_that_break_the_file_only_together_are_each_named(self):
        self.write("config.fish", b"set -g tide_x y\nset -g tide_z w\n")
        found = takeover.scan(self.folder, parses=lambda data: data.count(takeover.PREFIX) != 2)
        self.assertEqual(found.blockers, [
            f"config.fish line {number} is part of a command or string over several lines (fish could not read "
            "the file with it disabled); disable it yourself" for number in (1, 2)])
        self.assertEqual(found.lines, [])

    def test_enable_takes_back_only_what_witchy_added(self):
        self.assertEqual(takeover.enable(b"# witchy-disabled: a\n# a comment\n  # witchy-disabled: b\n"),
                         b"a\n# a comment\n  # witchy-disabled: b\n")


if __name__ == "__main__":
    unittest.main()
