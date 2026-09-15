package com.orderdelivery.orderservice.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.math.BigDecimal;

public class OrderItemRequest {

    @NotBlank(message = "productName is required")
    private String productName;

    @NotBlank(message = "category is required")
    private String category;

    @NotNull(message = "unitPrice is required")
    @DecimalMin(value = "0.0", message = "unitPrice must be >= 0")
    private BigDecimal unitPrice;

    @NotNull(message = "quantity is required")
    @Positive(message = "quantity must be > 0")
    private Integer quantity;

    public String getProductName() {
        return productName;
    }

    public void setProductName(String productName) {
        this.productName = productName;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public BigDecimal getUnitPrice() {
        return unitPrice;
    }

    public void setUnitPrice(BigDecimal unitPrice) {
        this.unitPrice = unitPrice;
    }

    public Integer getQuantity() {
        return quantity;
    }

    public void setQuantity(Integer quantity) {
        this.quantity = quantity;
    }
}
