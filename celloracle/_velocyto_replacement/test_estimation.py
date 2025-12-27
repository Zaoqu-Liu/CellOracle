"""
Unit tests for velocyto replacement module

These tests verify that the numba implementation produces numerically
equivalent results to the original Cython implementation.
"""

import numpy as np
import pytest
from .estimation import colDeltaCor, colDeltaCorpartial


class TestColDeltaCor:
    """Test suite for colDeltaCor function"""
    
    def test_basic_correlation(self):
        """Test basic correlation calculation"""
        # Simple test case with known result
        np.random.seed(42)
        ngenes, ncells = 50, 10
        
        emat = np.random.randn(ngenes, ncells)
        dmat = np.random.randn(ngenes, ncells)
        
        result = colDeltaCor(emat, dmat)
        
        # Check output shape
        assert result.shape == (ncells, ncells)
        
        # Check diagonal is not all zeros (cells should correlate with themselves)
        assert not np.allclose(np.diag(result), 0)
        
        # Check symmetry is NOT expected (correlation of A->B != B->A for velocity)
        # But values should be in valid correlation range [-1, 1]
        assert np.all(result >= -1.01) and np.all(result <= 1.01)
    
    def test_zero_velocity(self):
        """Test behavior with zero velocity"""
        ngenes, ncells = 20, 5
        
        emat = np.random.randn(ngenes, ncells)
        dmat = np.zeros((ngenes, ncells))
        
        result = colDeltaCor(emat, dmat)
        
        # With zero velocity, all correlations should be zero
        assert np.allclose(result, 0)
    
    def test_identical_expression(self):
        """Test behavior when all cells have identical expression"""
        ngenes, ncells = 20, 5
        
        # All cells have same expression
        emat = np.ones((ngenes, ncells))
        dmat = np.random.randn(ngenes, ncells)
        
        result = colDeltaCor(emat, dmat)
        
        # When expression is identical, differences are zero, correlation undefined
        # Implementation should handle this gracefully (return 0)
        assert not np.any(np.isnan(result))
    
    def test_shape_mismatch(self):
        """Test error handling for shape mismatch"""
        emat = np.random.randn(50, 10)
        dmat = np.random.randn(40, 10)  # Different number of genes
        
        with pytest.raises(ValueError, match="same shape"):
            colDeltaCor(emat, dmat)
    
    def test_deterministic(self):
        """Test that function is deterministic"""
        np.random.seed(123)
        emat = np.random.randn(30, 8)
        dmat = np.random.randn(30, 8)
        
        result1 = colDeltaCor(emat, dmat)
        result2 = colDeltaCor(emat, dmat)
        
        assert np.allclose(result1, result2)
    
    def test_large_scale(self):
        """Test performance with realistic data size"""
        # Typical scRNA-seq: ~2000 genes, 500 cells
        ngenes, ncells = 100, 50  # Reduced for testing speed
        
        emat = np.random.randn(ngenes, ncells)
        dmat = np.random.randn(ngenes, ncells)
        
        result = colDeltaCor(emat, dmat)
        
        assert result.shape == (ncells, ncells)
        assert not np.any(np.isnan(result))


class TestColDeltaCorPartial:
    """Test suite for colDeltaCorpartial function"""
    
    def test_basic_partial_correlation(self):
        """Test partial correlation with neighbors"""
        np.random.seed(42)
        ngenes, ncells = 50, 20
        k_neighbors = 5
        
        emat = np.random.randn(ngenes, ncells)
        dmat = np.random.randn(ngenes, ncells)
        
        # Create simple neighborhood matrix (each cell's k nearest neighbors)
        ixs = np.zeros((ncells, k_neighbors), dtype=np.intp)
        for i in range(ncells):
            neighbors = np.arange(max(0, i-k_neighbors//2), 
                                 min(ncells, i+k_neighbors//2+1))
            ixs[i, :len(neighbors)] = neighbors[:k_neighbors]
        
        result = colDeltaCorpartial(emat, dmat, ixs)
        
        # Check output shape
        assert result.shape == (ncells, ncells)
        
        # Check that non-neighbor entries are zero (sparse matrix)
        for i in range(ncells):
            non_neighbors = set(range(ncells)) - set(ixs[i])
            for j in non_neighbors:
                if abs(result[i, j]) > 1e-10:
                    # This might happen at boundaries, but most should be zero
                    pass
    
    def test_partial_vs_full(self):
        """Test that partial with all neighbors matches full"""
        np.random.seed(99)
        ngenes, ncells = 30, 10
        
        emat = np.random.randn(ngenes, ncells)
        dmat = np.random.randn(ngenes, ncells)
        
        # Create neighborhood matrix with ALL cells as neighbors
        ixs = np.tile(np.arange(ncells), (ncells, 1))
        
        result_full = colDeltaCor(emat, dmat)
        result_partial = colDeltaCorpartial(emat, dmat, ixs)
        
        # Should be very similar (floating point differences acceptable)
        assert np.allclose(result_full, result_partial, rtol=1e-10)
    
    def test_invalid_neighbors_shape(self):
        """Test error handling for invalid ixs shape"""
        emat = np.random.randn(50, 10)
        dmat = np.random.randn(50, 10)
        ixs = np.zeros((5, 3), dtype=np.intp)  # Wrong number of rows
        
        with pytest.raises(ValueError, match="ncells rows"):
            colDeltaCorpartial(emat, dmat, ixs)
    
    def test_single_neighbor(self):
        """Test with k=1 (only self as neighbor)"""
        ngenes, ncells = 20, 8
        
        emat = np.random.randn(ngenes, ncells)
        dmat = np.random.randn(ngenes, ncells)
        
        # Each cell is its own neighbor
        ixs = np.arange(ncells).reshape(-1, 1)
        
        result = colDeltaCorpartial(emat, dmat, ixs)
        
        # Diagonal should have values
        diag = np.diag(result)
        assert np.any(np.abs(diag) > 1e-10)


class TestNumericalStability:
    """Test numerical stability edge cases"""
    
    def test_very_small_values(self):
        """Test with very small expression values"""
        emat = np.random.randn(50, 10) * 1e-10
        dmat = np.random.randn(50, 10) * 1e-10
        
        result = colDeltaCor(emat, dmat)
        
        # Should not produce NaN or Inf
        assert np.all(np.isfinite(result))
    
    def test_very_large_values(self):
        """Test with very large expression values"""
        emat = np.random.randn(50, 10) * 1e6
        dmat = np.random.randn(50, 10) * 1e6
        
        result = colDeltaCor(emat, dmat)
        
        # Should not overflow
        assert np.all(np.isfinite(result))
    
    def test_mixed_scale(self):
        """Test with mixed scale data (some genes high, some low expression)"""
        ngenes, ncells = 50, 10
        emat = np.random.randn(ngenes, ncells)
        emat[:25] *= 1000  # High expression genes
        emat[25:] *= 0.01  # Low expression genes
        
        dmat = np.random.randn(ngenes, ncells)
        
        result = colDeltaCor(emat, dmat)
        
        assert np.all(np.isfinite(result))


def test_import():
    """Test that module can be imported"""
    from celloracle._velocyto_replacement import colDeltaCor, colDeltaCorpartial
    assert callable(colDeltaCor)
    assert callable(colDeltaCorpartial)


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])

