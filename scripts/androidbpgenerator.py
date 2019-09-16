#! /usr/bin/env python3
"""
* Copyright (c) 2019, Intel Corporation
*
* Permission is hereby granted, free of charge, to any person obtaining a
* copy of this software and associated documentation files (the "Software"),
* to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense,
* and/or sell copies of the Software, and to permit persons to whom the
* Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included
* in all copies or substantial portions of the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
* OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
* FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
* THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
* OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
* ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
* OTHER DEALINGS IN THE SOFTWARE.
"""

import os
import os.path as path
import re


INDENT = "    "
BUILD_DIR = "__build__"
TEMPLATE_DIR = "bp"
NOVERBOSE = " > /dev/null 2>&1;"


def remove(f):
    cmd = "rm -f " + f + NOVERBOSE
    os.system(cmd) 


class CCDefaults:
    # constructor
    def __init__(self, proj, defname, cflags = [], cppflags = [], clang_cflags = [],
        include_dirs = [], shared_libs = [], static_libs = [], bpfiles = []):
        self.templ = path.join(proj, TEMPLATE_DIR)
        self.proj = proj
        self.default_name = defname
        self.c_flag = cflags
        self.cpp_flag = cppflags
        self.clang_cflag = clang_cflags
        self.include_dir = include_dirs
        self.shared_lib = shared_libs
        self.static_lib = static_libs
        self.bp_file = bpfiles

    def getBpFilePath(self):
        return path.join(self.proj, "Android.bp")

    #major function
    def generate(self):
        if path.exists(self.proj) == False:
            raise Exception(self.proj + " not existed")
        # read template 
        with open(path.join(self.templ, "defaults.tpl")) as f:
            tpl = f.read()
        # remove all comment
        tpl = re.sub("#.*\n", "", tpl).strip()
        # replacement
        tpl = tpl.replace("@name", self.default_name)
        tpl = tpl.replace("@cflags", self.convertList2Str(self.c_flag))
        tpl = tpl.replace("@cppflags", self.convertList2Str(self.cpp_flag))
        tpl = tpl.replace("@clang_cflags", self.convertList2Str(self.clang_cflag))
        tpl = tpl.replace("@include_dirs", self.convertList2Str(self.include_dir))
        tpl = tpl.replace("@shared_libs", self.convertList2Str(self.shared_lib))
        tpl = tpl.replace("@static_libs", self.convertList2Str(self.static_lib))
        tpl = tpl.replace("@build", self.convertList2Str(self.bp_file, indent_num = 1))

        return tpl

    def convertList2Str(self, itemlist, indent_num = 2):
        str = ""

        for i, t in enumerate(itemlist):
            if 0 == len(t):
                continue
            str += INDENT * indent_num + "\"" + t + "\",\n"

        return INDENT * indent_num + "".join(str).strip()


class ModuleInfo:
    # constructor
    def __init__(self, modulename, bpfilename, cmakedir, moduletype, defaults,
        middledir = "", addsrc = [], addflags = [], addstatic = [], addshared = [],
        updateflags = {}, updatestatic = {}, updateshared = {}):
        self.Module_Name = modulename    # name of module
        self.Bp_File_Name = bpfilename    # BP file name
        self.Mid_Dir = middledir # some middle directory
        self.Build_Make = middledir + cmakedir + "build.make"    # building file in directory generated by cmake
        self.Flags_Make = middledir + cmakedir + "flags.make"    # flag-file in directory generated by cmake
        self.Module_Type = moduletype    # support: cc_library_shared, cc_library_static
        self.Defaults = INDENT * 2 + "\"" + defaults + "\","
        self.Add_Src = addsrc    # some additional source files
        self.Add_Flags = addflags    # some additional cflags/cppflags
        self.Add_Static = addstatic    # some additional static library
        self.Add_Shared = addshared    # some additional shared library
        self.Update_Flags = updateflags    # update some cflags/cppflags
        self.Update_Static = updatestatic    # update the dependent static libraries
        self.Update_Shared = updateshared    # update the dependent static libraries


class Generator:
    # constructor
    def __init__(self, src, root):
        # where is the major source file, and the directory to where *.bp should be put
        self.src = src
        # where to put build file and template
        self.build = path.join(root, BUILD_DIR)
        """where to put the template"""
        self.templ = path.join(src, TEMPLATE_DIR)
        # all submodule's info
        self.allmoduleinfo = {}
        #
        # self.allmoduledefaults = CCDefaults(...)

    #major function
    def generate(self, to_cmake = True, to_make = False):
        if path.exists(self.src) == False:
            raise Exception(self.src + " not existed")

        if to_cmake:
            self.generateMakefile(make = to_make)

        self.adjustFiles()

        allBPs = {}
        # sub-module" .bp
        for k in self.allmoduleinfo.keys():
            # the path of Android.bp
            bp = path.normpath(path.join(self.src, self.allmoduleinfo[k].Bp_File_Name))
            # read template
            with open(self.getTemplatePath()) as f:
                tpl = f.read()
            # remove all comment
            tpl = re.sub("#.*\n", "", tpl).strip()
            # an Android.bp is related to some module
            if bp in allBPs.keys():
                allBPs[bp] += "\n\n" + self.replaceTemplate(k, tpl)
            else:
                allBPs[bp] = self.replaceTemplate(k, tpl)
        # Android.bp
        allBPs[self.allmoduledefaults.getBpFilePath()] = self.allmoduledefaults.generate()

        for bp in allBPs.keys():
            # remove old Android.bp
            remove(bp)
            # create new Android.bp
            with open(bp, "w") as f:
                f.write(allBPs[bp])
            print(bp + " has been generated.")

    #virtuall functions
    def getTemplate(self):
        raise Exception("pure virtul function")

    def replaceTemplate(self, mode, tpl): 
        tpl = tpl.replace("@module", self.allmoduleinfo[mode].Module_Type)
        tpl = tpl.replace("@name", self.allmoduleinfo[mode].Module_Name)
        tpl = tpl.replace("@defaults", self.allmoduleinfo[mode].Defaults)
        tpl = tpl.replace("@srcs", self.getSources(mode))
        tpl = tpl.replace("@cflags", self.adjustFlags(mode, INDENT * 2 + "".join(self.getDefines(mode, "C_FLAGS") + self.getDefines(mode, "C_DEFINES")).strip(), is_add = False))
        tpl = tpl.replace("@cppflags", self.adjustFlags(mode, INDENT * 2 + "".join(self.getDefines(mode, "CXX_FLAGS") + self.getDefines(mode, "CXX_DEFINES")).strip()))
        tpl = tpl.replace("@local_include_dirs", INDENT * 2 + "".join(self.getIncludes(mode, "C_INCLUDES") + "\n" +  self.getIncludes(mode, "CXX_INCLUDES")).strip())
        tpl = tpl.replace("@shared_libs", INDENT * 2 + "".join(self.adjustLibrary(mode, self.getLibrary(mode, ".*?\\.so[.\d]*\\n", "\\.so)[.\d]*\\n", "\\.so[.\d]*"), False).strip()))
        tpl = tpl.replace("@static_libs", INDENT * 2 + "".join(self.adjustLibrary(mode, self.getLibrary(mode, ".*?\\.a\\n", "\\.a)\\n", "\\.a")).strip()))

        return tpl

    def getName(self):
        return self.getTemplate().split(".")[0]

    def getTemplatePath(self):
        return path.join(self.templ, self.getTemplate())

    def getBuildDir(self):
        return path.join(self.build, self.getName())

    def adjustSources(self, mode, all_sources):
        return all_sources

    def adjustIncludes(self, mode, all_includes):
        return all_includes

    def adjustFlags(self, mode, all_flags, is_add = True):
        return all_flags 

    def adjustLibrary(self, mode, all_libs, is_static = True):
        return all_libs

    def adjustFiles(self):
        return

    def getCmakeCmd(self):
        return "cmake -DCMAKE_BUILD_TYPE=Release " + self.src

    def generateMakefile(self, debug=False, make=False):
        #windows can help us debug the script and we do not want generate makefile on widnows
        if os.name == "nt":
            return

        verbose = ";" if debug else NOVERBOSE
        builddir = self.getBuildDir()
        # make quickly, but can't clear old makefile
        cmd = "rm " + path.join(builddir, "CMakeCache.txt") + verbose
        # clear old makefile, but need to cost some time
        #cmd = "rm -rf " + builddir + verbose
        cmd += "mkdir -p " + builddir + verbose
        cmd += "cd " + builddir + " && " + self.getCmakeCmd() + verbose
        # need to make this project
        if make: 
            print("It is making: " + self.src)
            cmd += "make -j$(nproc)"

        os.system(cmd)

    def getIncludes(self, mode, title):
        includestext = self.getDefines(mode, title)
        if (0 == len(includestext)):
            return ""

        lines = includestext.split("\n")
        includesfile = []

        for l in lines:
            if 0 == len(l):
                continue 
            #normpath will make sure we did not refer outside.
            p = path.normpath(l)
            j = p.find(self.src)
            #
            if 0 <= j:
                # check this path of include is existed, or not.
                k = p[j:].find('"') 
                if (0 <= k) and (True == path.isdir(p[j : (j + k)])):
                    includesfile.append(p[j:].replace(self.src, INDENT * 2 + "\""))

        return "\n".join(includesfile) if includesfile else ""

    def getDefines(self, mode, title):
        if not mode in self.allmoduleinfo.keys():
            raise Exception("Invalid index of module info")

        flagsfile = path.join(self.getBuildDir(), self.allmoduleinfo[mode].Flags_Make)
        with open(flagsfile) as f:
            text = f.read()

        lines = re.findall(title + " =.*\n", text)
        if (0 == len(lines)):
            return ""

        all_defines = ""

        for i, l in enumerate(lines):
            # 'strip' to remove the beginning and ending space
            l = l.replace(title + " = ", "").strip()
            if (0 == len(l)):
                continue

            all_defines += INDENT * 2 + "\"" + re.sub(r"[ ]+", "\",\n" + INDENT * 2 + "\"", re.sub("=\"\"", "=", l)) + "\",\n"

        return all_defines

    def getSources(self, mode):
        if not mode in self.allmoduleinfo.keys():
            raise Exception("Invalid index of module info")

        buildfile = path.join(self.getBuildDir(), self.allmoduleinfo[mode].Build_Make)
        with open(buildfile) as f:
            text = f.read()

        lines = re.findall(".*?: .*?CMakeFiles/.*?\\.dir/.*?\\.o\\n", text)
        lines = [l.replace(".o", "\",") for l in lines]

        self.adjustSources(mode, lines)

        #make source pretty
        return INDENT * 2 + "".join(lines).strip()

    def getLibrary(self, mode, reg1, reg2, reg3):
        if not mode in self.allmoduleinfo.keys():
            raise Exception("Invalid index of module info")

        buildfile = path.join(self.getBuildDir(), self.allmoduleinfo[mode].Build_Make)
        with open(buildfile) as f:
            text = f.read()

        lines = re.findall(reg1, text)
        if (0 == len(lines)):
            return ""

        all_lib = ""
        for i, l in enumerate(lines):
            if 0 == len(l) or re.search("(?<=" + self.allmoduleinfo[mode].Module_Name + reg2, l):
                continue

            j = l.rfind(": ")
            if 0 > j:
                continue

            l = l[(j + 2):]
            j = l.rfind('/')
            all_lib += INDENT * 2 + "\"" + re.sub(reg3, "\",", l[(j + 1):] if 0 <= j else l)

        return all_lib