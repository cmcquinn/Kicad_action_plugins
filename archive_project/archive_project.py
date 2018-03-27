import pcbnew
import os
import os.path
import shutil
import wx

def is_pcbnew_running():
    windows = wx.GetTopLevelWindows()
    if len(windows) == 0:
        return False
    else:
        return True



def archive_symbols(board, alt_files=False):
    # get project name
    project_name = os.path.basename(board.GetFileName()).split(".")[0]
    cache_lib_name = project_name + "-cache.lib"
    
    # load system symbol library table
    if is_pcbnew_running():
        sys_path = pcbnew.GetKicadConfigPath()
    else:
        # hardcode the path for my machine - testing works only on my machine
        sys_path = "C://Users//MitjaN//AppData//Roaming//kicad"

    global_sym_lib_file_path = sys_path + "//sym-lib-table"
    with open(global_sym_lib_file_path) as f:
        global_sym_lib_file = f.readlines()
    
    # get add library nicknames
    nicknames = []
    for line in global_sym_lib_file:
        nick_start = line.find("(name ")+6
        if nick_start >= 6:
            nick_stop = line.find(")", nick_start)
            nick = line[nick_start:nick_stop]
            nicknames.append(nick)
    
    # load project library table
    proj_path = os.path.dirname(os.path.abspath(board.GetFileName()))
    proj_sym_lib_file_path = proj_path + "//sym-lib-table"
    try:
        with open(proj_sym_lib_file_path) as f:
            project_sym_lib_file = f.readlines()
    # if file does not exists, create new
    except:
        new_sym_lib_file = [u"(sym_lib_table\n", u")\n"]
        with open(proj_sym_lib_file_path, "w") as f:
            f.writelines(new_sym_lib_file)
            project_sym_lib_file = new_sym_lib_file
    # append nicknames
    for line in project_sym_lib_file:
        nick_start = line.find("(name ")+6
        if nick_start >= 6:
            nick_stop = line.find(")", nick_start)
            nick = line[nick_start:nick_stop]
            nicknames.append(nick)

    # if there is already nickname cache but no actual cache-lib
    if "cache" in nicknames and cache_lib_name not in unicode(project_sym_lib_file):
            # warn the user and quite
            pass
            # TODO return proper error message
            return
    
    # if cache library is not on the list, put it there
    if cache_lib_name not in unicode(project_sym_lib_file):
        line_contents = "    (lib (name cache)(type Legacy)(uri ${KIPRJMOD}/" + cache_lib_name + ")(options \"\")(descr \"\"))\n"
        project_sym_lib_file.insert(1, line_contents)
        with open(proj_sym_lib_file_path, "w") as f:
            f.writelines(project_sym_lib_file)
    
    # load cache library
    proj_cache_ling_path = proj_path + "//" + cache_lib_name
    with open(proj_cache_ling_path) as f:
        project_cache_file = f.readlines()

    # get list of symbols in cache library
    cache_symbols = []
    for line in project_cache_file:
        line_contents = line.split()
        if line_contents[0] == "DEF":
            cache_symbols.append(line_contents[1])

    # find all .sch files
    all_sch_files = []
    for root, directories, filenames in os.walk(proj_path):
        for filename in filenames:
            if filename.endswith(".sch"):
                all_sch_files.append(os.path.join(root, filename))

    # go through each .sch file
    for filename in all_sch_files:
        with open(filename) as f:
            sch_file = f.readlines()

        sch_file_out = []
        # find line starting with L and next word until colon mathes library nickname
        for line in sch_file:
            line_contents = line.split()
            if line_contents[0] == "L" and line_contents[1].split(":")[0] in nicknames:
                # replace colon with underscore
                new_name = line_contents[1].replace(":", "_")
                # make sure that the symbol is in cache and append cache nickname
                if new_name in cache_symbols:
                    line_contents[1] = "cache:" + new_name
                # join line back again
                new_line = ' '.join(line_contents)
                sch_file_out.append(new_line+"\n")
            else:
                sch_file_out.append(line)

        # write
        if alt_files:
            filename = filename + "_alt"
        with open(filename, "w") as f:
            f.writelines(sch_file_out)
            pass
    pass


def archive_3D_models(board, alt_files=False):
    # load layout
    filename = board.GetFileName()
    with open(filename) as f:
        pcb_layout = f.readlines()

    # find all used models
    models = []
    for line in pcb_layout:
        index = line.find("(model")
        if index != -1:
            line_split = line.split()
            index = line_split.index("(model")
            model_path = line_split[index+1]
            models.append(model_path.rsplit(".", 1)[0])
    models = list(set(models))

    model_library_path = os.getenv("KISYS3DMOD")
    # if running standalone, enviroment variables might not be set
    if model_library_path is None:
        # hardcode the path for my machine - testing works only on my machine
        model_library_path = "D://Mitja//Plate//Kicad_libs//official_libs//Packages3D"

    # prepare folder for 3dmodels
    proj_path = os.path.dirname(os.path.abspath(board.GetFileName()))

    model_folder_path = proj_path + "//shapes3D"

    if not os.path.exists(model_folder_path):
        os.makedirs(model_folder_path)

    # go through the list of used models and replace enviroment variables
    cleaned_models = []
    for model in models:
        # check if path is encoded with variables
        if model[0:2] == "${":
            end_index = model.find("}")
            env_var = model[2:end_index]
            if env_var != "KISYS3DMOD":
                path = os.getenv(env_var)
            else:
                path = model_library_path
            if path is not None:
                model = path+model[end_index+1:]
                cleaned_models.append(model)
        # check if there is no path (model is local to project
        elif model == os.path.basename(model):
            model = proj_path + "//" + model
            cleaned_models.append(model)
        else:
            cleaned_models.append(model)

    # copy the models
    for model in cleaned_models:
        try:
            shutil.copy2(model + ".wrl", model_folder_path)
        except:
            pass
        try:
            shutil.copy2(model + ".step", model_folder_path)
        except:
            pass
        try:
            shutil.copy2(model + ".stp", model_folder_path)
        except:
            pass

    # generate output file with project relative path
    out_file = []
    for line in pcb_layout:
        line_new = line
        index = line.find("(model")
        if index != -1:
            line_split = line.split("(model")
            for model in cleaned_models:
                model = os.path.basename(model)
                if model in line_split[1]:
                    model_path = " ${KIPRJMOD}/" + "shapes3D/" + model + ".wrl"
                    line_split_split = line_split[1].split()
                    line_split_split[0] = model_path
                    line_split[1] = " ".join(line_split_split)
                    line_new = "(model".join(line_split) + "\n"
        out_file.append(line_new)
    # write
    if alt_files:
        filename = filename + "_alt"
    with open(filename, "w") as f:
        f.writelines(out_file)
    pass


def main():
    board = pcbnew.LoadBoard('archive_test_project.kicad_pcb')

    archive_symbols(board, True)

    archive_3D_models(board, True)


# for testing purposes only
if __name__ == "__main__":
    main()