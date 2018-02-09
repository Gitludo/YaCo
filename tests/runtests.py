#   Copyright (C) 2017 The YaCo Authors
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

#!/bin/python

import argparse
import difflib
import inspect
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

def get_ida_dir():
    try:
        return os.path.abspath(os.environ['IDA_DIR'])
    except KeyError:
        print("error: missing IDA_DIR environment variable")
        sys.exit(-1)

def remove_dir(dirname):
    # really remove read-only files
    def del_rw(action, name, exc):
        os.chmod(name, stat.S_IWRITE)
        os.remove(name)
    shutil.rmtree(dirname, onerror=del_rw)

def sysexec(cwd, *args):
    output = subprocess.check_output(*args, cwd=cwd, stderr=subprocess.STDOUT, shell=platform.system() != "Windows")
    if False:
        print output

ida_start = """
import idaapi
import idc
import sys

sys.path.append(idc.ARGV[1])
sys.path.append(idc.ARGV[2])
if idc.__EA64__:
    import YaToolsPy64 as ya
else:
    import YaToolsPy32 as ya
import YaCo

idc.Wait()
YaCo.start()
# start
"""

ida_end = """
# end
idc.SaveBase("")
idc.Exit(0)
"""

class Repo():

    def __init__(self, ctx, path):
        self.ctx = ctx
        self.path = path

    def run_script(self, script, init=False):
        import exec_ida
        args = ["-Oyaco:disable_plugin", "-A"]
        target = "Qt5Svgd.i64"
        if not init:
            target = "Qt5Svgd_local.i64"
        cmd = exec_ida.Exec(os.path.join(self.ctx.ida_dir, "ida64"), os.path.join(self.path, target), *args)
        cmd.set_idle(True)
        fd, fname = tempfile.mkstemp(dir=self.path, prefix="exec_", suffix=".py")
        os.write(fd, ida_start + script + ida_end)
        os.close(fd)
        cmd.with_script(fname, self.ctx.bin_dir, self.ctx.yaco_dir)
        err = cmd.run()
        self.ctx.assertEqual(err, None, "%s" % err)

    def run(self, *args):
        scripts = """
idc.SaveBase("")
"""
        todo = []
        for (script, check) in args:
            if check == None:
                scripts += script
                continue
            fd, fname = tempfile.mkstemp(dir=self.path, prefix="data_%02d_" % self.ctx.idx(), suffix=".xml")
            os.close(fd)
            scripts += """
with open("%s", "wb") as fh:
    fh.write(%s)
""" % (re.sub("\\\\", "/", fname), script)
            todo.append((check, fname))

        self.run_script(scripts)
        for (check, name) in todo:
            check(name)

ea_defmask = "(~0 & ~(1 << ya.OBJECT_TYPE_STRUCT) & ~(1 << ya.OBJECT_TYPE_ENUM)) & ~(1 << ya.OBJECT_TYPE_SEGMENT_CHUNK)"

class Fixture(unittest.TestCase):

    def setUp(self):
        args, _ = get_args()
        self.dirs = []
        self.counter = 0
        self.tests_dir = os.path.abspath(os.path.join(inspect.getsourcefile(lambda:0), ".."))
        self.yaco_dir = os.path.abspath(os.path.join(self.tests_dir, "..", "YaCo"))
        self.ida_dir = get_ida_dir()
        self.out_dir = os.path.abspath(os.path.join(self.tests_dir, "..", "out"))
        self.bin_dir = args.bindir
        sys.path.append(self.bin_dir)
        sys.path.append(self.yaco_dir)

    def tearDown(self):
        for d in self.dirs:
            remove_dir(d)

    def idx(self):
        self.counter += 1
        return self.counter - 1

    def script(self, script):
        self.enums = {}
        self.strucs = {}
        self.eas = {}
        return script, None

    def check_diff(self, want, filter=None):
        def check(name):
            data = None
            with open(name, "rb") as fh:
                data = fh.read()
                if filter:
                    data = filter(data)
            if data != want:
                self.fail("".join(difflib.unified_diff(want.splitlines(1), data.splitlines(1), name)))
        return check

    def filter_enum(self, d):
        # enum ordinals are unstable & depend on insertion order
        d = re.sub("address>[A-F0-9]+", "address>", d)
        return d

    def save_enum(self, name):
        script = "ya.export_xml_enum('%s')" % name
        def callback(filename):
            with open(filename, "rb") as fh:
                self.enums[name] = self.filter_enum(fh.read())
        return script, callback

    def check_enum(self, name):
        script = "ya.export_xml_enum('%s')" % name
        want = self.enums[name]
        return script, self.check_diff(want, filter=self.filter_enum)

    def filter_struc(self, d):
        # struc ordinals are unstable & depend on insertion order
        d = re.sub("address>[A-F0-9]+", "address>", d)
        return d

    def save_struc(self, name):
        script = "ya.export_xml_struc('%s')" % name
        def callback(filename):
            with open(filename, "rb") as fh:
                self.strucs[name] = self.filter_struc(fh.read())
        return script, callback

    def save_strucs(self):
        script = "ya.export_xml_strucs()"
        def callback(filename):
            with open(filename, "rb") as fh:
                self.strucs = self.filter_struc(fh.read())
        return script, callback

    def check_struc(self, name):
        script = "ya.export_xml_struc('%s')" % name
        want = self.strucs[name]
        return script, self.check_diff(want, filter=self.filter_struc)

    def check_strucs(self):
        script = "ya.export_xml_strucs()"
        want = self.strucs
        return script, self.check_diff(want, filter=self.filter_struc)

    def save_ea(self, ea):
        script = "ya.export_xml(0x%x, %s)" % (ea, ea_defmask)
        def callback(filename):
            with open(filename, "rb") as fh:
                self.eas[ea] = fh.read()
        return script, callback

    def check_ea(self, ea):
        script = "ya.export_xml(0x%x, %s)" % (ea, ea_defmask)
        want = self.eas[ea]
        return script, self.check_diff(want)

    def set_master(self, repo, master):
        sysexec(repo, ["git", "remote", "add", "origin", master])
        sysexec(repo, ["git", "fetch", "origin"])

    # set two linked repos
    def setup_repos(self):
        work_dir = tempfile.mkdtemp(prefix='repo_', dir=self.out_dir)
        self.dirs.append(work_dir)
        qt54 = os.path.join(self.tests_dir, "..", "testdata", "qt54_svg")
        a = os.path.abspath(os.path.join(work_dir, "a"))
        b = os.path.abspath(os.path.join(work_dir, "b"))
        c = os.path.abspath(os.path.join(work_dir, "c"))
        os.makedirs(a)
        shutil.copy(os.path.join(qt54, "Qt5Svgd.i64"), a)
        sysexec(a, ["git", "init"])
        sysexec(a, ["git", "add", "-A"])
        sysexec(a, ["git", "commit", "-m", "init"])
        sysexec(a, ["git", "clone", "--bare", ".", c])
        self.set_master(a, c)
        ra, rb = Repo(self, a), Repo(self, b)
        ra.run_script("", init=True)
        shutil.copytree(a, b)
        return ra, rb

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", default=False, help="list test targets")
    parser.add_argument("-v", "--verbose", type=int, default=2, help="verbosity level")
    parser.add_argument("-f", "--filter", type=str, default="", help="filter tests")
    cur_dir = os.path.abspath(os.path.join(inspect.getsourcefile(lambda:0), ".."))
    parser.add_argument("-b", "--bindir", type=os.path.abspath, default=os.path.abspath(os.path.join(cur_dir, "..", "bin", "yaco_x64", "YaTools", "bin")), help="binary directory")
    return parser.parse_args(), cur_dir

def get_tests(args, cur_dir):
    tests = unittest.TestSuite()
    for s in unittest.defaultTestLoader.discover(os.path.join(cur_dir, "tests")):
        for f in s:
            for test in f:
                if args.list:
                    print test.id()
                if test.id().find(args.filter) != -1:
                    tests.addTest(test)
    return tests

if __name__ == '__main__':
    args, cur_dir = get_args()
    tests = get_tests(args, cur_dir)
    if args.list:
        sys.exit(0)
    result = unittest.TextTestRunner(verbosity=args.verbose).run(tests)
    sys.exit(0 if not result.errors and not result.failures else -1)