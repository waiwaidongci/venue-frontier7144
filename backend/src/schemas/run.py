from pydantic import BaseModel,Field,model_validator
from src.constants.enums import INPUTS,OUTPUTS
class RunInput(BaseModel):
    name:str=Field(min_length=2,max_length=160)
    benchmark_id:int
    inputs:list[str]=Field(default_factory=lambda:list(INPUTS),min_length=1,max_length=2)
    outputs:list[str]=Field(default_factory=lambda:list(OUTPUTS),min_length=1,max_length=2)
    fixed_inputs:list[str]=Field(default_factory=list,max_length=2)
    sensitivity_count:int=Field(default=3,ge=1,le=3)
    @model_validator(mode='after')
    def keys_valid(self):
        if len(set(self.inputs))!=len(self.inputs) or len(set(self.outputs))!=len(self.outputs) or any(f not in INPUTS for f in self.inputs) or any(f not in OUTPUTS for f in self.outputs):raise ValueError('投入产出字段非法或重复')
        if len(set(self.fixed_inputs))!=len(self.fixed_inputs) or any(f not in self.inputs for f in self.fixed_inputs):raise ValueError('固定投入字段非法或不属于本次投入维度')
        if self.fixed_inputs and len(self.fixed_inputs)>=len(self.inputs):raise ValueError('至少保留一项可调整投入，不能把全部投入标为固定')
        return self
