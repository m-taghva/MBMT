import sys
import os
import subprocess
import time
import yaml
import argparse
import mrbench
import config_gen
import status_reporter
import monstaver
import analyzer

def load_config(config_file):
    with open(config_file, "r") as stream:
        try:
           data_loaded = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
           print(f"Error loading the configuration: {exc}")
           sys.exit(1)
    return data_loaded

def config_gen_agent(config_params):
    output_subdirs = {}
    input_files = config_params.get('conf_templates', [])
    output_path = config_params.get('output_path')
    for input_file in input_files:
        # Create output directory for each input file
        output_subdir = os.path.join(output_path, os.path.basename(input_file))
        print(output_subdir)
        config_gen.main(input_file, output_subdir)
        output_subdirs[os.path.basename(input_file)] = output_subdir
    return output_subdirs

def mrbench_agent(config_params, output_subdirs):
    all_start_times = [] ; all_end_times = []
    one_input_conf = config_params.get('input_config')
    result_dir = config_params.get('output_path')
    run_status_reporter = config_params.get('Status_Reporter', False)
    run_monstaver = config_params.get('monstaver', False)
    conf_ring_dir = config_params.get('conf_ring_dir')
    if one_input_conf:
       swift_configs = {}
       for filename in os.listdir(conf_ring_dir):
           swift_configs[filename] = os.path.join(conf_ring_dir, filename)
       mrbench.copy_swift_conf(swift_configs) 
       start_time, end_time, result_file_path = mrbench.submit(one_input_conf, result_dir)
       all_start_times.append(start_time) ; all_end_times.append(end_time)
       if run_status_reporter:
          status_reporter.main(path_dir=result_file_path, time_range=f"{start_time},{end_time}", img=True)
       if run_monstaver:
          monstaver.backup(time_range=f"{start_time},{end_time}", inputs=[result_file_path], delete=True)        
    else:
       Total_index = 0
       swift_configs = {}
       if output_subdirs["workloads.xml"]==None:
           print("There isn't any workload!!!")
           exit()
       if len(output_subdirs)>1:
          Total_index = 1
       conf_dir = output_subdirs["workloads.xml"].split("workloads")[0]
       print(conf_dir)
       for key in output_subdirs:
           if key != "workloads.xml":
              Total_index *=len(os.listdir(output_subdirs[key]))
              swift_configs[key]=""
       for i in range(Total_index):
           m=1
           for key in swift_configs:
               list_dir = os.listdir(output_subdirs[key])
               print(list_dir)
               swift_configs[key] = os.path.join(conf_dir,key,list_dir[(i//m)%len(list_dir)])
               m *= len(list_dir)
           print(swift_configs)
           mrbench.copy_swift_conf(swift_configs)
           for key, subdir in output_subdirs.items():
               if key == "workloads.xml":
                  print(subdir)
                  for test_config in os.listdir(subdir):
                      test_config_path = os.path.join(subdir, test_config)
                      print(test_config_path)
                      start_time, end_time, result_file_path = mrbench.submit(test_config_path, result_dir)
                      all_start_times.append(start_time) ; all_end_times.append(end_time)
                      if run_status_reporter:
                         status_reporter.main(path_dir=result_file_path, time_range=f"{start_time},{end_time}", img=True)  
                      if run_monstaver:
                         monstaver.backup(time_range=f"{start_time},{end_time}", inputs=[result_file_path], delete=True)                     
    # Extract first start time and last end time
    first_start_time = all_start_times[0] ; last_end_time = all_end_times[-1] 
    return first_start_time, last_end_time

def monstaver_agent(config_params, first_start_time, last_end_time):
    operation = config_params.get('operation')
    batch_mode = config_params.get('batch_mode', False)
    times_file = config_params.get('times')
    input_path = config_params.get('input_path')
    if times_file:
       with open(times_file, 'r') as file:
            times = file.readlines()
            for time_range in times:
                start_time, end_time = time_range.strip().split(',')
                if operation == "backup":
                   monstaver.backup(time_range=f"{start_time},{end_time}", inputs=[input_path], delete=True)
                elif operation == "restore":
                     monstaver.restore()          
    elif operation == "backup":
         if batch_mode:
            monstaver.backup(time_range=f"{first_start_time},{last_end_time}", inputs=[input_path], delete=True)
    elif operation == "restore":
         monstaver.restore()

def status_reporter_agent(config_params):
    result_dir = config_params.get('output_path')
    times_file = config_params.get('times')
    if times_file:
       with open(times_file, 'r') as file:
            times = file.readlines()
            for time_range in times:
                start_time, end_time = time_range.strip().split(',')
                status_reporter.main(path_dir=result_dir, time_range=f"{start_time},{end_time}", img=True)

def status_analyzer_agent(config_params):
    result_dir = config_params.get('input_path')
    merge = config_params.get('merge', False)
    merge_csv = config_params.get('merge_csv')
    analyze = config_params.get('analyze', False)
    analyze_csv = config_params.get('analyze_csv')
    transform_dir = config_params.get('transform')
    if merge:
       analyzer.main_merge(input_directory=result_dir, selected_csv=merge_csv)
       time.sleep(10)
    if analyze:
       analyzer.main_analyze(csv_original=f"{result_dir}/{analyze_csv}", transformation_directory=transform_dir)

def report_recorder_agent(config_params):
    input_template = config_params.get('input_template')
    output_html = config_params.get('output_html')
    kateb_title = config_params.get('kateb_title')
    pybot = f"python3 ./../../pywikibot/report_recorder.py -it {input_template} -oh {output_html} -kt {kateb_title}"
    subprocess.call(pybot, shell=True)

def main():
    data_loaded = load_config(config_file)
    if 'scenario' in data_loaded:
        output_subdirs = None
        first_start_time = None
        last_end_time = None
        for task in data_loaded['scenario']:            
            try:
                if 'Config_gen' in task:
                    config_params = task['Config_gen']
                    output_subdirs = config_gen_agent(config_params)
                elif 'Mrbench' in task:
                      config_params = task['Mrbench']
                      first_start_time, last_end_time = mrbench_agent(config_params, output_subdirs)
                elif 'Status-Reporter' in task:
                      config_params = task['Status-Reporter']
                      status_reporter_agent(config_params)
                elif 'Monstaver' in task:
                      config_params = task['Monstaver']
                      monstaver_agent(config_params, first_start_time, last_end_time)
                elif 'Status_Analyzer' in task:
                      config_params = task['Status_Analyzer']
                      status_analyzer_agent(config_params)
                elif 'Report_Recorder' in task:
                      config_params = task['Report_Recorder']
                      report_recorder_agent(config_params)
                else:
                     print(f"Unknown task: {task}")
            except Exception as e:
                 print(f"Error executing task: {task}. Error: {str(e)}")
    else:
        print(f"\033[91mNo scenario found in the configuration file.\033[0m")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='kara tools manager')
    parser.add_argument('-sn', '--scenario_name', help='input scenario path')
    args = parser.parse_args()
    config_file = args.scenario_name
    main()
