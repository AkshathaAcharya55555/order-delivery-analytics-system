package com.orderdelivery.orderservice.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "order_items")
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "order_item_id")
    private Long orderItemId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    @Column(name = "product_name", nullable = false, length = 150)
    private String productName;

    @Column(name = "category", nullable = false, length = 50)
    private String category;

    @Column(name = "unit_price", nullable = false, precision = 10, scale = 2)
    private BigDecimal unitPrice;

    @Column(name = "quantity", nullable = false)
    private Integer quantity;

    // line_total is a DB-generated column (unit_price * quantity); never written by this app.
    @Column(name = "line_total", insertable = false, updatable = false, precision = 10, scale = 2)
    private BigDecimal lineTotal;

    protected OrderItem() {
    }

    public OrderItem(String productName, String category, BigDecimal unitPrice, Integer quantity) {
        this.productName = productName;
        this.category = category;
        this.unitPrice = unitPrice;
        this.quantity = quantity;
    }

    public Long getOrderItemId() {
        return orderItemId;
    }

    public Order getOrder() {
        return order;
    }

    public void setOrder(Order order) {
        this.order = order;
    }

    public String getProductName() {
        return productName;
    }

    public String getCategory() {
        return category;
    }

    public BigDecimal getUnitPrice() {
        return unitPrice;
    }

    public Integer getQuantity() {
        return quantity;
    }

    /** Computed locally (unit_price * quantity) rather than reading the DB-generated
     * column back, since the value is fully known at construction time. */
    public BigDecimal computeLineTotal() {
        return unitPrice.multiply(BigDecimal.valueOf(quantity));
    }
}
