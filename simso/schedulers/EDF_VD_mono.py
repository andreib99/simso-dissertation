"""
Earliest Deadline First with Virtual Deadlines algorithm for uniprocessor architectures.
"""
import random

import numpy as np

from simso.core import Scheduler
from simso.schedulers import scheduler


@scheduler("simso.schedulers.EDF_VD_mono")
class EDF_VD_mono(Scheduler):

    def init(self):
        self.ready_list = []
        self.mode = 0
        self.K = self.task_list[0].nr_crit_levels

        if not self.passed_pesimistic_test():
            print("Error")

        self._pre_runtime_processing()

    def passed_pesimistic_test(self):
        if sum([t.list_wcets[t.crit_level] / float(t.period) for t in self.task_list]) <= 1:
            return 1
        return 0

    def _pre_runtime_processing(self):
        def _cpu_levels_utilization(min_level, max_level):
            return sum(
                [task.list_wcets[task.crit_level] / float(task.period) for task in self.task_list if
                 min_level <= task.crit_level <= max_level])

        for k in range(self.K):
            u_lo = _cpu_levels_utilization(0, k)
            u_hi = _cpu_levels_utilization(k + 1, self.K)
            a = u_hi / float(1 - u_lo)
            b = (1 - u_hi) / float(u_lo)
            if u_lo < 1 and a <= b:
                x = 1
                while x <= 0 or x >= 1:
                    x = random.uniform(a, b)
                for t in self.task_list:
                    if t.crit_level > k:
                        t.deadline = t.period * x

    def on_activate(self, job):
        if job.task.enabled:
            self.ready_list.append(job)
            choices = [0, 1]
            weights = [0.8, 0.2]
            if job.task.crit_level == self.mode:
                wcets = job.task.list_wcets
                deviations = job.task.wcet_deviations
                if np.random.choice(choices, 1, p=weights) == 0:
                    et = random.uniform(wcets[self.mode] - deviations[self.mode], wcets[self.mode])
                else:
                    et = random.uniform(wcets[self.mode], wcets[self.mode] + deviations[self.mode])
            else:
                et = job.wcet
            job._etm.et[job] = et * self.sim.cycles_per_ms

        job.cpu.resched()

    def on_terminated(self, job):
        if job in self.ready_list:
            self.ready_list.remove(job)
        task = job.task
        if self.mode == task.crit_level and job.computation_time > task.list_wcets[self.mode]:
            self.mode += 1
            for t in self.task_list:
                if t.crit_level < self.mode:
                    t.enabled = False
                if t.crit_level == self.mode:
                    t.deadline = t.period

        job.cpu.resched()

    def schedule(self, cpu):
        if self.ready_list:
            # job with the highest priority
            job = min(self.ready_list, key=lambda x: x.absolute_deadline)
        else:
            job = None

        return (job, cpu)
