"""
Partitionned EDF-VD using PartitionedScheduler.
"""
from simso.core.Scheduler import SchedulerInfo
from simso.utils import PartitionedScheduler
from simso.utils.PartitionedScheduler import decreasing_first_fit
from simso.schedulers import scheduler

@scheduler("simso.schedulers.P_EDF_VD_FF_D")
class P_EDF_VD_FF_D(PartitionedScheduler):
    def init(self):
        PartitionedScheduler.init(
            self, SchedulerInfo("simso.schedulers.EDF_VD_mono"), decreasing_first_fit)
