"""Prediction request -> validated inputs -> inference -> response with an input summary.

Errors become ApiError with a stable code; invalid clinical fields are listed in field_errors. The response
keeps the original keys (probabilities, predicted_class, run_id, has_overlay) and adds `inputs`.
"""
import uuid

from pulmo_cases import ApiError
from pulmo_clinical import ClinicalError, clinical_summary
from pulmo_runtime import catalog, infer

CT_ONLY_INPUTS = dict(used=False, note='CT-only model: clinical inputs were not used.')


def model_mode(model):
    mode = next((r['mode'] for r in catalog() if r['id'] == model), None)
    if mode is None:
        raise ApiError(400, 'model_unavailable', 'Select an available trained model.', dict(model=model))
    return mode


def predict_case(case, model, clinical, explain=True):
    fusion = model_mode(model) == 'fusion'
    try:
        inputs = clinical_summary(clinical) if fusion else CT_ONLY_INPUTS
        result, cam = infer(case['stack'], model, clinical, explain)
    except ClinicalError as exc:
        raise ApiError(400, 'invalid_clinical', f'Check the clinical inputs: {exc}', exc.field_errors) from None
    except ValueError as exc:
        raise ApiError(400, 'invalid_request', str(exc)) from None
    except RuntimeError:
        raise ApiError(503, 'inference_failed', 'Inference failed. If GPU memory is full, stop training and retry.') from None
    result.update(case=case['name'], source=case['source'], clinical=clinical if fusion else {}, inputs=inputs,
                  severity='Not assessed', disclaimer='Research use only. Not a clinical diagnosis.')
    run_id = uuid.uuid4().hex
    # Bind images to this exact inference so changing inputs cannot show a stale explanation.
    case['prediction'] = dict(id=run_id, cam=cam, result=result)
    return dict(**result, run_id=run_id, has_overlay=cam is not None)
