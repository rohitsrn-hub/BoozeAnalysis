import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Calendar, FileText, Loader2 } from 'lucide-react';

const PeriodSelectionModal = ({ 
  isOpen, 
  onClose, 
  onGenerateReport, 
  periods = [], 
  reportType = 'pdf',
  isGenerating = false 
}) => {
  const [selectedPeriods, setSelectedPeriods] = useState([]);

  // Reset selection when modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedPeriods([]);
    }
  }, [isOpen]);

  const togglePeriod = (period) => {
    setSelectedPeriods(prev => {
      if (prev.find(p => p.id === period.id)) {
        return prev.filter(p => p.id !== period.id);
      } else {
        return [...prev, period];
      }
    });
  };

  const handleGenerate = () => {
    if (selectedPeriods.length === 0) {
      return;
    }
    onGenerateReport(selectedPeriods, reportType);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-indigo-600" />
            Select Sales Period(s) for Report
          </DialogTitle>
          <DialogDescription>
            Select one or more periods to include in your report. Multiple periods will be aggregated.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Period Selection */}
          <div className="space-y-3">
            <h4 className="font-medium text-gray-900">Available Periods</h4>
            
            {periods.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Calendar className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                <p>No sales periods available</p>
              </div>
            ) : (
              <div className="grid gap-3">
                {periods.map((period) => {
                  const isSelected = selectedPeriods.find(p => p.id === period.id);
                  
                  return (
                    <div
                      key={period.id}
                      onClick={() => togglePeriod(period)}
                      className={`p-4 rounded-lg border-2 cursor-pointer transition-all duration-200 ${
                        isSelected
                          ? 'border-indigo-500 bg-indigo-50'
                          : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                            isSelected ? 'border-indigo-600 bg-indigo-600' : 'border-gray-300'
                          }`}>
                            {isSelected && (
                              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </div>
                          <div>
                            <div className="font-semibold text-gray-900">{period.period_name}</div>
                            <div className="text-sm text-gray-600">
                              {period.d1_date} to {period.dl_date}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-medium text-gray-700">
                            {period.total_records} brands
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Selection Summary */}
          {selectedPeriods.length > 0 && (
            <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-blue-900">Selected Periods</h4>
                  <p className="text-sm text-blue-700 mt-1">
                    {selectedPeriods.length === 1
                      ? 'Generating report for 1 period'
                      : `Aggregating data from ${selectedPeriods.length} periods`}
                  </p>
                </div>
                <Badge variant="secondary" className="text-lg px-3 py-1">
                  {selectedPeriods.length}
                </Badge>
              </div>
              
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedPeriods.map((period) => (
                  <Badge key={period.id} variant="outline" className="text-xs">
                    {period.period_name}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end space-x-3 pt-4 border-t">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isGenerating}
          >
            Cancel
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={selectedPeriods.length === 0 || isGenerating}
            className="bg-indigo-600 hover:bg-indigo-700"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <FileText className="w-4 h-4 mr-2" />
                Generate {reportType.toUpperCase()} Report
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default PeriodSelectionModal;
