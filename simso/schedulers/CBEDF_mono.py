"""
Earliest Deadline First algorithm for uniprocessor architectures.
"""
import math
import random

import numpy as np

from simso.core import Scheduler, Timer
from simso.schedulers import scheduler


def lcm_multiple(numbers):
    def lcm(a, b):
        return abs(a * b) // math.gcd(a, b)

    lcm_result = numbers[0]
    for num in numbers[1:]:
        lcm_result = lcm(lcm_result, num)

    return lcm_result


@scheduler("simso.schedulers.CBEDF_mono")
class CBEDF_mono(Scheduler):
    def init(self):
        self.counter = 0
        self.mode = 0
        self.waiting_schedule = False
        self.lo_ready_list = []
        self.hi_ready_list = []
        self.job_counts = {}
        self.remaining_slack = 0

        for t in self.task_list:
            t.wcet = t.list_wcets[0]

        task_periods = [int(t.period) for t in self.task_list]
        self.hyperperiod = lcm_multiple(task_periods)

        self.nr_task_jobs = {}
        for idx, t in enumerate(self.task_list):
            self.nr_task_jobs[t] = int(self.hyperperiod / t.period)

        lo_jobs = []
        hi_jobs = []
        for i in self.nr_task_jobs:
            for j in range(self.nr_task_jobs[i]):
                if i.crit_level == 1:
                    hi_jobs.append({"task": i, "nr_job": j})
                else:
                    lo_jobs.append({"task": i, "nr_job": j, "es": 0})

        self.lo_jobs = sorted(lo_jobs, key=lambda x: x["task"].deadline + x["task"].period * x["nr_job"])
        self.hi_jobs = self._calculate_slacks(hi_jobs)
        for t in self.task_list:
            self.job_counts[t] = 0

    def _calculate_slacks(self, jobs):
        jobs = sorted(jobs, key=lambda x: x["task"].deadline + x["task"].period * x["nr_job"])
        for i in reversed(range(len(jobs))):
            if i == len(jobs) - 1:
                jobs[i]["is"] = 0
            else:
                is_job = jobs[i]["task"].deadline + jobs[i]["task"].period * jobs[i]["nr_job"] - (
                        jobs[i + 1]["task"].deadline + jobs[i + 1]["task"].period * jobs[i + 1]["nr_job"]) + \
                        jobs[i + 1]["is"] + jobs[i + 1]["task"].list_wcets[1]
                if is_job > 0:
                    jobs[i]["is"] = is_job
                else:
                    jobs[i]["is"] = 0

        for i in range(len(jobs)):
            if i == 0:
                jobs[i]["es"] = 0
            else:
                es_job = jobs[i]["task"].deadline + jobs[i]["task"].period * jobs[i]["nr_job"] - (
                            jobs[i - 1]["task"].deadline + jobs[i - 1]["task"].period * jobs[i - 1]["nr_job"]) - \
                         jobs[i]["is"] - jobs[i]["task"].list_wcets[1]
                if es_job > 0:
                    jobs[i]["es"] = es_job
                else:
                    jobs[i]["es"] = 0
        return jobs

    def reschedule(self, cpu=None):
        """
        Ask for a scheduling decision. Don't call if not necessary.
        """
        if not self.waiting_schedule:
            if cpu is None:
                cpu = self.processors[0]
            cpu.resched()
        self.waiting_schedule = True

    def _calculate_job_execution_time(self, job):
        task = job.task
        choices = [0, 1]
        weights = [0.5, 0.5]
        wcets = task.list_wcets
        deviations = task.wcet_deviations
        if np.random.choice(choices, 1, p=weights) == 0 or self.mode == task.nr_crit_levels - 1:
            et = random.randint(wcets[self.mode] - deviations[self.mode], wcets[self.mode])
            while et == 0:
                et = random.randint(wcets[self.mode] - deviations[self.mode], wcets[self.mode])
        else:
            et = random.randint(wcets[self.mode], wcets[self.mode] + deviations[self.mode])
            while et > wcets[1]:
                et = random.randint(wcets[self.mode], wcets[self.mode] + deviations[self.mode])

        job._etm.et[job] = et * self.sim.cycles_per_ms

        return job

    def on_activate(self, job):
        job = self._calculate_job_execution_time(job)

        if job.task.crit_level == 1:
            for idx, i in enumerate(self.hi_jobs):
                if i["task"] == job.task and self.job_counts[job.task] % self.nr_task_jobs[job.task] == i["nr_job"]:
                    job.es = i["es"]
                    self.job_counts[job.task] = self.job_counts[job.task] + 1
                    if idx >= len(self.hi_ready_list):
                        self.hi_ready_list.append(job)
                    else:
                        self.hi_ready_list.insert(idx, job)
                    break
        else:
            for idx, i in enumerate(self.lo_jobs):
                if i["task"] == job.task and self.job_counts[job.task] % self.nr_task_jobs[job.task] == i["nr_job"]:
                    job.es = i["es"]
                    self.job_counts[job.task] = self.job_counts[job.task] + 1
                    if idx >= len(self.lo_ready_list):
                        self.lo_ready_list.append(job)
                    else:
                        self.lo_ready_list.insert(idx, job)
                    break
        self.reschedule()

    def on_terminated(self, job):
        if job.computation_time > job.task.list_wcets[self.mode] and self.mode != job.task.nr_crit_levels - 1:
            self._mode_switch(job)
        if job.task.crit_level == 1:
            if int(job.task.list_wcets[1] - job.computation_time) >= 1:
                self.remaining_slack = int(job.task.list_wcets[1] - job.computation_time)

    def _mode_switch(self, job):
        self.mode = self.mode + 1
        for t in self.task_list:
            t.wcet = t.list_wcets[self.mode]

        for idx, j in enumerate(self.hi_ready_list):
            if j != job:
                self.hi_ready_list[idx] = self._calculate_job_execution_time(j)
        for idx, j in enumerate(self.lo_ready_list):
            if j != job:
                self.lo_ready_list[idx] = self._calculate_job_execution_time(j)

    def _get_current_job(self):
        hi_job = next((j for j in self.hi_ready_list if j.is_active()), None)
        lo_job = next((j for j in self.lo_ready_list if j.is_active()), None)

        if hi_job:
            hi_job_index = self.hi_ready_list.index(hi_job)
            if lo_job:
                if self.remaining_slack > 0:
                    self.remaining_slack = self.remaining_slack - 1
                    job = lo_job
                elif hi_job.es > 0:
                    job = lo_job
                    self.hi_ready_list[hi_job_index].es = hi_job.es - 1
                else:
                    job = hi_job
            else:
                job = hi_job
        else:
            if lo_job:
                job = lo_job
            else:
                job = None

        return job

    def schedule(self, cpu):
        if self.counter % self.hyperperiod == 0:
            self.remaining_slack = 0
        self.waiting_schedule = False

        self.timer_a = Timer(self.sim, CBEDF_mono.reschedule, (self,),
                             1000000, cpu=cpu, in_ms=False)
        self.timer_a.start()

        job = self._get_current_job()
        self.counter = self.counter + 1
        return (job, cpu)
