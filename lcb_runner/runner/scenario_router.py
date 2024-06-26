from typing import Union

from lcb_runner.utils.scenarios import Scenario
from lcb_runner.lm_styles import LanguageModel
from lcb_runner.evaluation import (
    codegen_metrics, 
    test_output_metrics,
    code_execution_metrics,
)

from lcb_runner.prompts import (
    format_prompt_generation, 
    format_prompt_test_output,
    format_prompt_execution,
    format_prompt_execution_cot,
)
from lcb_runner.utils.extraction_utils import (
    extract_code, 
    extract_test_output_code,
    extract_execution_code,
)
from lcb_runner.benchmarks import (
    CodeGenerationProblem,
    TestOutputPredictionProblem,
    CodeExecutionProblem,
    load_code_generation_dataset,
    load_test_prediction_dataset,
    load_code_execution_dataset,
)

# BenchMarkType = list[CodeGenerationProblem | TestOutputPredictionProblem]
BenchMarkType = list[Union[CodeGenerationProblem, CodeExecutionProblem, TestOutputPredictionProblem]]


def build_prompt_benchmark(
    scenario: Scenario,
    cot_code_execution : bool,
) -> tuple[list[CodeExecutionProblem] | list[CodeGenerationProblem] | list[TestOutputPredictionProblem], callable]:
    if scenario == Scenario.codegeneration:
        benchmark = load_code_generation_dataset()
        benchmark = sorted(benchmark, key=lambda x: x.question_id)
        format_prompt = format_prompt_generation
    elif scenario == Scenario.testoutputprediction:
        benchmark = load_test_prediction_dataset()
        benchmark = sorted(benchmark, key=lambda x: (x.question_id, x.test_id))
        format_prompt = format_prompt_test_output
    elif scenario == Scenario.codeexecution:
        benchmark = load_code_execution_dataset()
        benchmark = sorted(benchmark, key=lambda x: int(x.id.split("_")[1]))
        if cot_code_execution:
            format_prompt = format_prompt_execution_cot
        else:
            format_prompt = format_prompt_execution
    else:
        raise ValueError(f"Scenario {scenario} not implemented")

    return benchmark, format_prompt


def combine_results(scenario: Scenario, results: list[list[str]], model: LanguageModel, cot_code_execution: bool = False):
    if scenario == Scenario.codegeneration:
        combined_results = [
            (
                outputs_list,
                [extract_code(output, model.model_style) for output in outputs_list],
            )
            for outputs_list in results
        ]
    elif scenario == Scenario.testoutputprediction:
        combined_results = [
            (
                outputs_list,
                [
                    extract_test_output_code(output, model.model_style)
                    for output in outputs_list
                ],
            )
            for outputs_list in results
        ]
    elif scenario == Scenario.codeexecution:
        combined_results = [
            (
                outputs_list,
                [
                    extract_execution_code(output, model.model_style, cot=cot_code_execution) 
                    for output in outputs_list
                ],
            )
            for outputs_list in results
        ]
    else:
        raise ValueError(f"Scenario {scenario} not implemented")

    return combined_results


def sort_and_extract_save_results(scenario: Scenario, save_results: list[dict]):
    if scenario == Scenario.codegeneration:
        save_results = sorted(save_results, key=lambda x: x["question_id"])
        combined_results = [
            (save_result_instance["output_list"], save_result_instance["code_list"])
            for save_result_instance in save_results
        ]

    elif scenario == Scenario.testoutputprediction:
        save_results = sorted(
            save_results, key=lambda x: (x["question_id"], x["test_id"])
        )
        combined_results = [
            (save_result_instance["output_list"], save_result_instance["pred_list"])
            for save_result_instance in save_results
        ]
    
    elif scenario == Scenario.codeexecution:
        save_results = sorted(save_results, key=lambda x: int(x["id"].split("_")[1]))
        combined_results = [
            (save_result_instance["output_list"], save_result_instance["pred_list"])
            for save_result_instance in save_results
        ]

    else:
        raise ValueError(f"Scenario {scenario} not implemented")

    return save_results, combined_results


def get_metrics(
    scenario: Scenario,
    args,
    benchmark: list[CodeGenerationProblem | CodeExecutionProblem | TestOutputPredictionProblem],
    combined_results,
):
    if scenario == Scenario.codegeneration:
        eval_samples = [instance.get_evaluation_sample() for instance in benchmark]
        generations = [extracted for _, extracted in combined_results]
        metrics = codegen_metrics(
            eval_samples,
            generations,
            num_process_evaluate=args.num_process_evaluate,
            timeout=args.timeout,
        )

    elif args.scenario == Scenario.testoutputprediction:
        eval_samples = [instance.get_evaluation_sample() for instance in benchmark]
        generations = [extracted for _, extracted in combined_results]
        metrics = test_output_metrics(
            eval_samples,
            generations,
            k_list=[1, 5],
        )
    
    elif args.scenario == Scenario.codeexecution:
        eval_samples = [instance.get_evaluation_sample() for instance in benchmark]
        generations = [extracted for _, extracted in combined_results]
        for g in generations:
            print(g)
        metrics = code_execution_metrics(
            eval_samples,
            generations,
        )

    else:
        raise ValueError(f"Scenario {scenario} not implemented")

    print(metrics[0]["pass@1"])

    return metrics
