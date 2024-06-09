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
        self.max_crit_level = max([t.crit_level for t in self.task_list], default=None)
        self.min_crit_level = min([t.crit_level for t in self.task_list], default=None)
        self.mode = self.min_crit_level or 0
        self.K = self.task_list[0].nr_crit_levels
        if self.min_crit_level != self.max_crit_level:
            if not self.passed_pesimistic_test():
                print("Error: Total utilization over 100%!")
                self.sim.logger.log("Error: Total utilization over 100%!")

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

        for k in range(self.min_crit_level, self.K):
            u_lo = _cpu_levels_utilization(self.min_crit_level, k)
            if u_lo == 0:
                continue
            u_hi = _cpu_levels_utilization(k + 1, self.K)
            if u_lo >= 1 or u_hi > 1:
                continue
            a = u_hi / float(1 - u_lo)
            b = (1 - u_hi) / float(u_lo)
            if u_lo < 1 and a <= b and (a < 1 or b > 0) and a < 1:
                x = 2
                while x <= 0 or x >= 1:
                    x = random.uniform(a, b)
                for t in self.task_list:
                    if t.crit_level > k:
                        t.deadline = t.period * x

    def on_activate(self, job):
        task = job.task
        if task.enabled:
            self.ready_list.append(job)
            choices = [0, 1]
            weights = [0.9, 0.1]
            wcets = task.list_wcets
            deviations = task.wcet_deviations
            if np.random.choice(choices, 1, p=weights) == 0 or self.mode == task.nr_crit_levels - 1:
                et = random.uniform(wcets[self.mode] - deviations[self.mode], wcets[self.mode])
            else:
                et = random.uniform(wcets[self.mode], wcets[self.mode] + deviations[self.mode])

            job._etm.et[job] = et * self.sim.cycles_per_ms

        job.cpu.resched()

    def on_terminated(self, job):
        if job in self.ready_list:
            self.ready_list.remove(job)
        task = job.task
        if job.computation_time > task.list_wcets[self.mode] and self.mode != task.nr_crit_levels - 1:
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
