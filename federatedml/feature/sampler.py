#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from arch.api import eggroll
from arch.api import federation
from sklearn.utils import resample
from federatedml.util import consts
from federatedml.util.transfer_variable import SampleTransferVariable
from federatedml.util.param_checker import SampleParamChecker


class RandomSampler(object):
    def __init__(self, fraction=0.1, random_state=None, method="downsample"):
        self.fraction = fraction
        self.random_state = random_state
        self.method = method

    def sample(self, data_inst, sample_ids=None):
        if sample_ids is None:
            sample_data_inst, sample_ids = self.__sample(data_inst)
            return sample_data_inst, sample_ids
        else:
            new_data_inst = self.__sample(data_inst, sample_ids)
            return new_data_inst

    def __sample(self, data_inst, sample_ids=None):
        return_sample_ids = False
        if self.method == "downsample":
            if sample_ids is None:
                return_sample_ids = True
                idset = [key for key, value in data_inst.mapValues(lambda val: None).collect()]
                if self.fraction < 0 or self.fraction > 1:
                    raise ValueError("sapmle fractions should be a numeric number between 0 and 1inclusive")

                sample_num = max(1, int(self.fraction * len(idset)))

                sample_ids = resample(idset,
                                      replace=False,
                                      n_samples=sample_num,
                                      random_state=self.random_state)

            sample_dtable = eggroll.parallelize(zip(sample_ids, range(len(sample_ids))),
                                                include_key=True,
                                                partition=data_inst._partitions)
            new_data_inst = data_inst.join(sample_dtable, lambda v1, v2: v1)

            if return_sample_ids:
                return new_data_inst, sample_ids
            else:
                return new_data_inst

        elif self.method == "upsample":
            data_set = list(data_inst.collect())
            idset = [key for (key, value) in data_set]
            id_maps = dict(zip(idset, range(len(idset))))

            if sample_ids is None:
                return_sample_ids = True
                if self.fraction <= 0:
                    raise ValueError("sapmle fractions should be a numeric number large than 0")

                sample_num = int(self.fraction * len(idset))
                sample_ids = resample(idset,
                                      replace=True,
                                      n_samples=sample_num,
                                      random_state=self.random_state)

            new_data = []
            for i in range(len(sample_ids)):
                index = id_maps[sample_ids[i]]
                new_data.append((i, data_set[index][1]))

            new_data_inst = eggroll.parallelize(new_data,
                                                include_key=True,
                                                partition=data_inst._partitions)

            if return_sample_ids:
                return new_data_inst, sample_ids
            else:
                return new_data_inst

        else:
            raise ValueError("random sampler not support method {} yet".format(self.method))


class StratifiedSampler(object):
    def __init__(self, fractions=None, random_state=None, method="downsample"):
        self.fractions = fractions
        self.label_mapping = None
        if fractions:
            self.label_mapping = [label for (label, frac) in fractions]
        
        self.random_state = random_state
        self.method = method

    def sample(self, data_inst, sample_ids=None):
        if sample_ids is None:
            sample_data_inst, sample_ids = self.__sample(data_inst)
            return sample_data_inst, sample_ids
        else:
            new_data_inst = self.__sample(data_inst, sample_ids)
            return new_data_inst

    def __sample(self, data_inst, sample_ids=None):
        return_sample_ids = False
        if self.method == "downsample":
            if sample_ids is None:
                idset = [[] for i in range(len(self.fractions))]
                for label, fraction in self.fractions:
                    if fraction < 0 or fraction > 1:
                        raise ValueError("sapmle fractions should be a numeric number between 0 and 1inclusive")
                
                return_sample_ids = True
                for key, inst in data_inst.collect():
                    label = inst.label
                    if label not in self.label_mapping:
                        raise ValueError("label not specify sample rate! check it please")
                    idset[self.label_mapping[label]].append(key)

                sample_ids = []
                for i in range(len(idset)):
                    if idset[i]:
                        sample_num = max(1, int(self.fractions[i][1] * len(idset[i])))

                        _sample_ids = resample(idset[i],
                                               replace=False,
                                               n_samples=sample_num,
                                               random_state=self.random_state)

                    sample_ids.extend(_sample_ids)

            sample_dtable = eggroll.parallelize(zip(sample_ids, range(len(sample_ids))),
                                                include_key=True,
                                                partition=data_inst._partitions)
            new_data_inst = data_inst.join(sample_dtable, lambda v1, v2: v1)

            if return_sample_ids:
                return new_data_inst, sample_ids
            else:
                return new_data_inst

        elif self.method == "upsample":
            data_set = list(data_inst.collect())
            ids = [key for (key, inst) in data_set]
            id_maps = dict(zip(ids, range(len(ids))))

            return_sample_ids = False

            if sample_ids is None:
                idset = [[] for i in range(len(self.fractions))]
                for label, fraction in self.fractions:
                    if fraction <= 0:
                        raise ValueError("sapmle fractions should be a numeric number greater than 0")
                
                for key, inst in data_set:
                    label = inst.label
                    if label not in self.label_mapping:
                        raise ValueError("label not specify sample rate! check it please")
                    idset[self.label_mapping[label]].append(key)

                return_sample_ids = True

                sample_ids = []
                for i in range(len(idset)):
                    if idset[i]:
                        sample_num = max(1, int(self.fractions[i][1] * len(idset[i])))

                        _sample_ids = resample(idset[i],
                                               replace=True,
                                               n_samples=sample_num,
                                               random_state=self.random_state)

                        sample_ids.extend(_sample_ids)


            new_data = []
            for i in range(len(sample_ids)):
                index = id_maps[sample_ids[i]]
                new_data.append((i, data_set[index][1]))

            new_data_inst = eggroll.parallelize(new_data,
                                                include_key=True,
                                                partition=data_inst._partitions)

            if return_sample_ids:
                return new_data_inst, sample_ids
            else:
                return new_data_inst

        else:
            raise ValueError("Stratified sampler not support method {} yet".format(self.method))


class Sampler(object):
    def __init__(self, sample_param):
        SampleParamChecker.check_param(sample_param)
        if sample_param.mode == "random":
            self.sampler = RandomSampler(sample_param.fractions,
                                         sample_param.random_state,
                                         sample_param.method)

        elif sample_param.mode == "stratified":
            self.sampler = StratifiedSampler(sample_param.fractions,
                                             sample_param.random_state,
                                             sample_param.method)

        else:
            raise ValueError("{} sampler not support yet".format(sample_param.mde))

        self.flowid = None

    def sample(self, data_inst, sample_ids=None):
        ori_schema = data_inst.schema
        sample_data = self.sampler.sample(data_inst, sample_ids)

        try:
            if len(sample_data) == 2:
                sample_data[0].schema = ori_schema
        except:
            sample_data.schema = ori_schema

        return sample_data

    def set_flowid(self, flowid="samole"):
        self.flowid = flowid

    def sync_sample_ids(self, sample_ids):
        transfer_inst = SampleTransferVariable()
        
        federation.remote(obj=sample_ids,
                          name=transfer_inst.sample_ids.name,
                          tag=transfer_inst.generate_transferid(transfer_inst.sample_ids, self.flowid),
                          role="host")

    def recv_sample_ids(self):
        transfer_inst = SampleTransferVariable()
        
        sample_ids = federation.get(name=transfer_inst.sample_ids.name,
                                    tag=transfer_inst.generate_transferid(transfer_inst.sample_ids, self.flowid),
                                    idx=0)

        return sample_ids

    def run(self, data_inst, task_type, task_role):
        if task_type not in [consts.HOMO, consts.HETERO]:
            raise ValueError("{} task type not support yet".format(task_type))
        
        if task_type == consts.HOMO:
            return self.sample(data_inst)[0]
        
        elif task_type == consts.HETERO:
            if task_role == consts.GUEST:
                sample_data_inst, sample_ids = self.sample(data_inst)
                self.sync_sample_ids(sample_ids)

            elif task_role == consts.HOST:
                sample_ids = self.recv_sample_ids()
                sample_data_inst = self.sample(data_inst, sample_ids)
            
            else:
                raise ValueError("{} role not support yet".format(task_role))

            return sample_data_inst

