import numpy as np
import sys
import time
from model.Configuration import Configuration
from algorithm import Cso
from HtmlOutput import HtmlOutput

# 
# python run_GASshedule.py <GaSchedule.json> <output.html>
#

if __name__=='__main__':
    file_name = sys.argv[1] 
    start_time = int(round(time.time() * 1000))
    configuration = Configuration()
    configuration.parseFile(file_name)
    alg = Cso.Cso(configuration)
    alg.run()
    html_result = HtmlOutput.getResult(alg.result)
    with open(sys.argv[2], 'w') as f:
        f.write(html_result)
