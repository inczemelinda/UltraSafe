import { Check } from "lucide-react";

export type WizardStep = {
  id: string;
  label: string;
};

type WizardStepInput = WizardStep | string;
type WizardStepValue = number | string;

type WizardStepperProps = {
  ariaLabel?: string;
  className?: string;
  completedSteps?: readonly WizardStepValue[];
  currentStep: WizardStepValue;
  onStepClick?: (step: WizardStep, index: number) => void;
  steps: readonly WizardStepInput[];
};

export function WizardStepper({
  ariaLabel = "Wizard progress",
  className = "",
  completedSteps,
  currentStep,
  onStepClick,
  steps
}: WizardStepperProps) {
  const normalizedSteps = steps.map((step) => (
    typeof step === "string" ? { id: step, label: step } : step
  ));
  const currentIndex = getCurrentStepIndex(normalizedSteps, currentStep);

  return (
    <nav
      aria-label={ariaLabel}
      className={`rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-4 shadow-sm sm:px-4 ${className}`}
    >
      <ol className={`grid ${stepperGridClass(normalizedSteps.length)} gap-x-2 gap-y-4`}>
        {normalizedSteps.map((step, index) => {
          const completed = isCompletedStep(step, index, currentIndex, completedSteps);
          const current = index === currentIndex;
          const connectorClass = completed ? "bg-emerald-300" : "bg-slate-200";
          const circleClass = completed
            ? "border-emerald-500 bg-emerald-500 text-white"
            : current
              ? "border-orange-600 bg-orange-600 text-white shadow-sm shadow-orange-200"
              : "border-slate-300 bg-white text-slate-400";
          const labelClass = completed
            ? "text-emerald-700"
            : current
              ? "text-orange-600"
              : "text-slate-500";
          const content = (
            <>
              <span
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 text-sm font-bold transition-colors ${circleClass}`}
              >
                {completed ? <Check className="h-4 w-4" /> : index + 1}
              </span>
              <span className={`flex min-h-8 max-w-full items-start justify-center text-center text-xs font-semibold leading-4 sm:text-sm ${labelClass}`}>
                {step.label}
              </span>
            </>
          );

          return (
            <li aria-current={current ? "step" : undefined} className="relative min-w-0" key={step.id}>
              {index < normalizedSteps.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={`absolute left-1/2 top-5 hidden h-0.5 w-full lg:block ${connectorClass}`}
                />
              ) : null}
              {onStepClick ? (
                <button
                  className="relative z-10 flex w-full flex-col items-center gap-2 rounded-lg text-center transition focus:outline-none focus:ring-4 focus:ring-orange-100"
                  onClick={() => onStepClick(step, index)}
                  type="button"
                >
                  {content}
                </button>
              ) : (
                <div className="relative z-10 flex flex-col items-center gap-2 text-center">
                  {content}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function getCurrentStepIndex(steps: WizardStep[], currentStep: WizardStepValue) {
  if (typeof currentStep === "number") {
    return Math.max(0, Math.min(currentStep, steps.length - 1));
  }

  const index = steps.findIndex((step) => step.id === currentStep || step.label === currentStep);
  return index >= 0 ? index : 0;
}

function isCompletedStep(
  step: WizardStep,
  index: number,
  currentIndex: number,
  completedSteps?: readonly WizardStepValue[]
) {
  if (!completedSteps) return index < currentIndex;
  return completedSteps.some((completedStep) => (
    typeof completedStep === "number"
      ? completedStep === index
      : completedStep === step.id || completedStep === step.label
  ));
}

function stepperGridClass(stepCount: number) {
  if (stepCount <= 4) return "grid-cols-2 sm:grid-cols-4";
  if (stepCount <= 6) return "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6";
  if (stepCount <= 8) return "grid-cols-2 sm:grid-cols-4 lg:grid-cols-8";
  return "grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-10";
}

